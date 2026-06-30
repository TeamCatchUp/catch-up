import asyncio
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Literal

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.configs.config import settings
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.confluence.client import ConfluenceApiError
from catchup.connectors.confluence.client import ConfluenceRateLimitError
from catchup.connectors.confluence.schemas import ConfluenceBlogPostResponse
from catchup.connectors.confluence.schemas import ConfluenceCommentResponse
from catchup.connectors.confluence.schemas import ConfluenceLabelResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.db.confluence import domain_repository
from catchup.db.engine import SessionLocal
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.document_builders.confluence import ConfluenceTransformer
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)

logger = structlog.get_logger(__name__)

@dataclass(slots=True, frozen=True)
class ConfluenceRecordGapItem:
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ConfluenceRecordGapReport:
    records: list[ConfluenceRecordGapItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ConfluenceRecordRetryItem:
    record_type: str
    requested_ids: list[str] = field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    remaining_missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ConfluenceRecordRetryResult:
    records: list[ConfluenceRecordRetryItem] = field(default_factory=list)

class ConfluenceIngestionService:
    def __init__(
        self,
        cloud_id: str,
        token_provider: AtlassianTokenProvider,
        site_url: str,
        repository: PGVectorRepository,
    ):
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")

        self.client = ConfluenceApiClient(cloud_id, token_provider)
        self.transformer = ConfluenceTransformer()
        self.repository = repository

    @staticmethod
    def _is_retryable_connector_error(exc: Exception) -> bool:
        return isinstance(exc, ConfluenceRateLimitError) or (
            isinstance(exc, ConfluenceApiError) and exc.retry_after is not None
        )

    async def initialize(self) -> None:
        logger.info(
            "confluence_ingestion_service_initialize_started",
            connector="confluence",
            scope_id=self.cloud_id,
        )
        self.repository.ensure_initialized()
        logger.info(
            "confluence_ingestion_service_initialized",
            connector="confluence",
            scope_id=self.cloud_id,
        )

    def _resolve_sync_from_dt(
        self,
        sync_days: int | None,
    ) -> datetime:
        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        return datetime.now(timezone.utc) - timedelta(days=days)

    @staticmethod
    def _sort_record_ids(record_ids: set[str]) -> list[str]:
        def _key(value: str) -> tuple[int, int | str]:
            try:
                return (0, int(value))
            except ValueError:
                return (1, value)

        return sorted(record_ids, key=_key)

    @staticmethod
    def _build_gap_item(
        *,
        record_type: str,
        expected_ids: list[str],
        stored_ids: list[str],
        stored_count: int,
    ) -> ConfluenceRecordGapItem:
        missing_ids = ConfluenceIngestionService._sort_record_ids(
            set(expected_ids) - set(stored_ids)
        )
        return ConfluenceRecordGapItem(
            record_type=record_type,
            expected_count=len(expected_ids),
            stored_count=stored_count,
            missing_count=len(missing_ids),
            missing_ids=missing_ids,
        )

    def _load_space_context_db(
        self,
        space_key: str,
    ) -> tuple[str, str | None, dict[str, str | None]]:
        with SessionLocal() as db:
            space_id_map = domain_repository.get_space_id_map(db, self.cloud_id, [space_key])
            space_name_map = domain_repository.get_space_name_map(db, self.cloud_id, [space_key])
            space_id = space_id_map.get(space_key)
            if not space_id:
                raise ValueError(f"confluence space not found: space_key={space_key}")
            user_name_map = self._load_user_name_map(db)
            return space_id, space_name_map.get(space_key), user_name_map

    async def _load_space_context(
        self,
        space_key: str,
    ) -> tuple[str, str | None, dict[str, str | None]]:
        return await asyncio.to_thread(self._load_space_context_db, space_key)

    async def _collect_page_ids(
        self,
        *,
        space_id: str,
        since: datetime | None,
    ) -> list[str]:
        page_ids: list[str] = []
        should_stop = False

        async for batch in self.client.iter_pages(
            space_id=space_id,
            body_format="storage",
        ):
            for raw_page in batch:
                page = ConfluencePageResponse.model_validate(raw_page)
                modified_at = parse_atlassian_datetime(
                    page.version.created_at if page.version else None
                )
                if since and modified_at and modified_at < since:
                    should_stop = True
                    continue
                page_ids.append(page.id)
            if should_stop:
                break

        return page_ids

    async def _collect_blogpost_ids(
        self,
        *,
        space_id: str,
        since: datetime | None,
    ) -> list[str]:
        blogpost_ids: list[str] = []
        should_stop = False

        async for batch in self.client.iter_blogposts(
            space_id=space_id,
            body_format="storage",
        ):
            for raw_blogpost in batch:
                blogpost = ConfluenceBlogPostResponse.model_validate(raw_blogpost)
                modified_at = parse_atlassian_datetime(
                    blogpost.version.created_at if blogpost.version else None
                )
                if since and modified_at and modified_at < since:
                    should_stop = True
                    continue
                blogpost_ids.append(blogpost.id)
            if should_stop:
                break

        return blogpost_ids

    async def _store_transform_result(
        self,
        *,
        entity_type: str,
        content_id: str,
        space_key: str,
        transform_result: ConfluenceTransformResult,
        audit_context: SyncAuditContext | None = None,
    ) -> tuple[str, ...]:
        documents = transform_result.documents
        await self.repository.delete_by_id_prefix(
            f"confluence:{entity_type}:{content_id}:chunk:"
        )
        if not documents:
            return ()

        doc_ids = [doc.id for doc in documents]
        embeddings = await self._generate_embeddings(
            transform_result,
            entity_type=entity_type,
            content_id=content_id,
            space_key=space_key,
            audit_context=audit_context,
        )
        await self.repository.store_with_embeddings(
            documents,
            embeddings,
            doc_ids,
            audit_context=audit_context,
            context=(
                f"entity_type={entity_type},space_key={space_key},"
                f"doc_count={len(documents)}"
            ),
        )
        return ()

    def _transform_page_blocking(
        self,
        page: ConfluencePageResponse,
        *,
        space_key: str,
        space_name: str | None = None,
        labels: list[str] | None = None,
        footer_comments: list[ConfluenceCommentResponse] | None = None,
        inline_comments: list[ConfluenceCommentResponse] | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
        return self.transformer.transform_page(
            page,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            site_url=self.site_url,
            user_name_map=user_name_map,
        )

    def _transform_blogpost_blocking(
        self,
        blogpost: ConfluenceBlogPostResponse,
        *,
        space_key: str,
        space_name: str | None = None,
        labels: list[str] | None = None,
        footer_comments: list[ConfluenceCommentResponse] | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
        return self.transformer.transform_blogpost(
            blogpost,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            site_url=self.site_url,
            user_name_map=user_name_map,
        )


    async def _process_page(
            self,
            page: ConfluencePageResponse,
            space_key: str,
            space_name: str | None = None,
            user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
        
        footer_comments, inline_comments, labels = await self._fetch_supplementary(
            api_content_type="pages",
            content_id=page.id,
        )

        return await run_in_threadpool(
            self._transform_page_blocking,
            page,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            user_name_map=user_name_map,
        )
    
    async def _process_blogpost(
        self,
        blogpost: ConfluenceBlogPostResponse,
        space_key: str,
        space_name: str | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:

        footer_comments, _, labels = await self._fetch_supplementary(
            api_content_type="blogposts",
            content_id=blogpost.id,
        )

        return await run_in_threadpool(
            self._transform_blogpost_blocking,
            blogpost,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            user_name_map=user_name_map,
        )

    async def _retry_record_batch(
        self,
        *,
        space_key: str,
        space_name: str | None,
        user_name_map: dict[str, str | None],
        record_type: Literal["page", "blogpost"],
        requested_ids: list[str],
    ) -> ConfluenceRecordRetryItem:
        async def _retry_one(content_id: str) -> tuple[str, bool]:
            try:
                if record_type == "page":
                    raw_content = await self.client.get_page_by_id(
                        content_id,
                        body_format="storage",
                    )
                    content = ConfluencePageResponse.model_validate(raw_content)
                    transform_result = await self._process_page(
                        content,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )
                else:
                    raw_content = await self.client.get_blogpost_by_id(
                        content_id,
                        body_format="storage",
                    )
                    content = ConfluenceBlogPostResponse.model_validate(raw_content)
                    transform_result = await self._process_blogpost(
                        content,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )

                if not transform_result.documents:
                    logger.info(
                        "confluence_repair_retry_no_documents",
                        connector="confluence",
                        entity_type=record_type,
                        scope_id=self.cloud_id,
                        target_id=space_key,
                        content_id=content_id,
                    )
                    return content_id, True

                await self._store_transform_result(
                    entity_type=record_type,
                    content_id=content.id,
                    space_key=space_key,
                    transform_result=transform_result,
                    audit_context=None,
                )
                return content_id, True
            except Exception as exc:
                if self._is_retryable_connector_error(exc):
                    raise
                logger.warning(
                    "confluence_repair_retry_failed",
                    connector="confluence",
                    entity_type=record_type,
                    scope_id=self.cloud_id,
                    target_id=space_key,
                    content_id=content_id,
                    exception_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=True,
                )
                return content_id, False

        succeeded_count = 0
        failed_ids: list[str] = []
        batch_size = max(1, settings.CONFLUENCE_SYNC_MAX_CONCURRENT_REQUEST)

        for start in range(0, len(requested_ids), batch_size):
            batch_ids = requested_ids[start : start + batch_size]
            results = await asyncio.gather(*[_retry_one(content_id) for content_id in batch_ids])

            for content_id, succeeded in results:
                if succeeded:
                    succeeded_count += 1
                    continue
                failed_ids.append(content_id)

        return ConfluenceRecordRetryItem(
            record_type=record_type,
            requested_ids=requested_ids,
            retried_count=len(requested_ids),
            succeeded_count=succeeded_count,
            failed_ids=self._sort_record_ids(set(failed_ids)),
        )

    async def build_record_gap_report(
        self,
        *,
        space_key: str,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
    ) -> ConfluenceRecordGapReport:
        since = sync_from_dt or self._resolve_sync_from_dt(sync_days)
        space_id, _space_name, _user_name_map = await self._load_space_context(space_key)

        (
            expected_page_ids,
            expected_blogpost_ids,
            stored_page_ids,
            stored_blogpost_ids,
        ) = await asyncio.gather(
            self._collect_page_ids(
                space_id=space_id,
                since=since,
            ),
            self._collect_blogpost_ids(
                space_id=space_id,
                since=since,
            ),
            self.repository.list_confluence_record_ids(
                space_key=space_key,
                entity_type="page",
                since=since,
            ),
            self.repository.list_confluence_record_ids(
                space_key=space_key,
                entity_type="blogpost",
                since=since,
            ),
        )

        return ConfluenceRecordGapReport(
            records=[
                self._build_gap_item(
                    record_type="page",
                    expected_ids=expected_page_ids,
                    stored_ids=stored_page_ids,
                    stored_count=len(stored_page_ids),
                ),
                self._build_gap_item(
                    record_type="blogpost",
                    expected_ids=expected_blogpost_ids,
                    stored_ids=stored_blogpost_ids,
                    stored_count=len(stored_blogpost_ids),
                ),
            ]
        )

    async def retry_missing_records(
        self,
        *,
        space_key: str,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
        page_ids: list[str] | None = None,
        blogpost_ids: list[str] | None = None,
    ) -> ConfluenceRecordRetryResult:
        requested_page_ids = list(page_ids or [])
        requested_blogpost_ids = list(blogpost_ids or [])
        result_items: list[ConfluenceRecordRetryItem] = []

        _space_id, space_name, user_name_map = await self._load_space_context(space_key)

        if requested_page_ids:
            result_items.append(
                await self._retry_record_batch(
                    space_key=space_key,
                    space_name=space_name,
                    user_name_map=user_name_map,
                    record_type="page",
                    requested_ids=requested_page_ids,
                )
            )

        if requested_blogpost_ids:
            result_items.append(
                await self._retry_record_batch(
                    space_key=space_key,
                    space_name=space_name,
                    user_name_map=user_name_map,
                    record_type="blogpost",
                    requested_ids=requested_blogpost_ids,
                )
            )

        return ConfluenceRecordRetryResult(records=result_items)

    def _load_user_name_map(self, db: Session) -> dict[str, str | None]:
        """
        ConfluenceUsers 테이블에서 account_type이 'atlassian'인 사용자만 로드해
        account_id → display_name 매핑을 만든다. Full Sync에서 작성자 이름 주입용으로 사용.
        """
        users = domain_repository.get_users_by_cloud_id(db, self.cloud_id)
        mapping = {
            user.account_id: (user.display_name or user.public_name)
            for user in users
            if user.account_type == "atlassian"
        }
        logger.info(
            "confluence_user_cache_loaded",
            connector="confluence",
            scope_id=self.cloud_id,
            user_count=len(mapping),
        )
        return mapping

    async def _fetch_supplementary(
            self,
            api_content_type: str,
            content_id: str,
    ) -> tuple[
        list[ConfluenceCommentResponse],        # footer_comments
        list[ConfluenceCommentResponse],        # inline_comments
        list[str],                              # labels
    ]:
        entity_type = "page" if api_content_type == "pages" else "blogpost"
        tasks = [
            self.client.get_content_footer_comments(api_content_type, content_id),
            self.client.get_content_labels(api_content_type, content_id),
        ]

        if api_content_type == "pages":
            tasks.append(
                self.client.get_content_inline_comments(api_content_type, content_id)
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception) and self._is_retryable_connector_error(result):
                raise result

        for result in results:
            if isinstance(result, Exception):
                logger.warning(
                    "confluence_supplementary_fetch_failed",
                    connector="confluence",
                    scope_id=self.cloud_id,
                    entity_type=entity_type,
                    api_content_type=api_content_type,
                    content_id=content_id,
                    exception_type=type(result).__name__,
                    error=str(result),
                )

        footer_comments = []
        if isinstance(results[0], list):
            footer_comments = [ConfluenceCommentResponse.model_validate(r) for r in results[0]]

        labels = []
        if isinstance(results[1], list):
            labels = [ConfluenceLabelResponse.model_validate(r).name for r in results[1]]

        inline_comments = []
        if (
            api_content_type == "pages"
            and len(results) > 2
            and isinstance(results[2], list)
        ):
            inline_comments = [ConfluenceCommentResponse.model_validate(r) for r in results[2]]
        
        return footer_comments, inline_comments, labels
    
    async def _generate_embeddings(
        self,
        transform_result: ConfluenceTransformResult,
        *,
        entity_type: str,
        content_id: str,
        space_key: str,
        audit_context: SyncAuditContext | None = None,
    ) -> list[list[float]]:
        documents = transform_result.documents
        if not documents:
            return []

        embeddings = await self.repository.generate_embeddings(
            documents,
            audit_context=audit_context,
            context=(
                f"entity_type={entity_type},space_key={space_key},"
                f"doc_count={len(documents)},embed_mode=text_only"
            ),
        )
        image_document_count = sum(
            1 for document in documents if document.metadata.get("has_images")
        )

        logger.info(
            "confluence_embeddings_generated",
            connector="confluence",
            entity_type=entity_type,
            scope_id=self.cloud_id,
            target_id=space_key,
            content_id=content_id,
            document_count=len(documents),
            embed_mode="text_only",
            image_document_count=image_document_count,
        )

        missing_embeddings = [
            index for index, embedding in enumerate(embeddings) if embedding is None
        ]
        if missing_embeddings:
            raise RuntimeError(
                "Missing confluence embeddings after text-only processing: "
                f"content_id={content_id}, indices={missing_embeddings}"
            )

        return embeddings
