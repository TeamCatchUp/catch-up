import asyncio
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from catchup.components.embedder.service import AwsBedrockEmbeddingService
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.confluence.schemas import (
    ConfluenceAttachmentResponse,
    ConfluenceBlogPostResponse,
    ConfluenceCommentResponse,
    ConfluenceLabelResponse,
    ConfluencePageResponse,
)
from catchup.connectors.confluence.transformers import (
    ConfluenceAttachmentAsset,
    ConfluenceTransformer,
    ConfluenceTransformResult,
)
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.db.confluence import domain_repository
from catchup.db.engine import SessionLocal
from catchup.configs.config import settings
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import TargetSyncResult

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


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
        embedding_service: AwsBedrockEmbeddingService,
    ):
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")

        self.client = ConfluenceApiClient(cloud_id, token_provider)
        self.transformer = ConfluenceTransformer()
        self.repository = repository
        self.embedding_service = embedding_service

    async def initialize(self) -> None:
        logger.info(f"[CONFLUENCE][SERVICE] Ensuring initialization: cloud_id={self.cloud_id}")
        self.repository.ensure_initialized()
        logger.info(f"[CONFLUENCE][SERVICE] Initialized Successfully: cloud_id={self.cloud_id}")

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

    def _load_space_context_sync(
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
        return await asyncio.to_thread(self._load_space_context_sync, space_key)

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
    ) -> None:
        documents = transform_result.documents
        if not documents:
            return

        doc_ids = [doc.id for doc in documents]
        await self.repository.delete_by_id_prefix(
            f"confluence:{entity_type}:{content_id}:chunk:"
        )
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

    # ================================================================
    # Full Sync
    # ================================================================
    async def full_sync(
            self,
            db: Session,
            space_keys: list[str] | None = None,
            sync_from_dt: datetime | None = None,
            audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        sync_from = sync_from_dt or (
            datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
        )

        if space_keys is None:
            normalized_space_keys = [
                (space.space_key or "").strip()
                for space in domain_repository.get_spaces_by_cloud_id(db, self.cloud_id)
                if (space.space_key or "").strip()
            ]
        else:
            normalized_space_keys = [
                key.strip()
                for key in space_keys
                if key and key.strip()
            ]
            normalized_space_keys = list(dict.fromkeys(normalized_space_keys))

        logger.info(
            f"[CONFLUENCE][FULL SYNC] Started: "
            f"cloud_id={self.cloud_id}, spaces={normalized_space_keys or 'all'} since={sync_from.isoformat()}"
        )

        results: dict[str, Any] = {
            "pages": {"synced": 0, "errors": 0},
            "blogposts": {"synced": 0, "errors": 0},
        }

        try:
            if not normalized_space_keys:
                logger.warning(f"[CONFLUENCE][FULL SYNC] No spaces to sync: cloud_id={self.cloud_id}")
                return TargetSyncResult(skipped=True)

            space_id_map = domain_repository.get_space_id_map(
                db, self.cloud_id, normalized_space_keys,
            )
            space_name_map = domain_repository.get_space_name_map(
                db, self.cloud_id, normalized_space_keys,
            )
            if not space_id_map:
                logger.error(
                    "[CONFLUENCE][FULL SYNC] No spaces found from requested keys: cloud_id=%s, requested_space_keys=%s",
                    self.cloud_id,
                    normalized_space_keys,
                )
                results["pages"]["errors"] += max(1, len(normalized_space_keys))
                results["blogposts"]["errors"] += max(1, len(normalized_space_keys))
                return TargetSyncResult(
                    error_count=(
                        int(results["pages"]["errors"]) + int(results["blogposts"]["errors"])
                    )
                )

            missing_space_keys = [
                space_key
                for space_key in normalized_space_keys
                if space_key not in space_id_map
            ]
            if missing_space_keys:
                logger.error(
                    "[CONFLUENCE][FULL SYNC] Some spaces are missing from metadata snapshot: cloud_id=%s, missing_space_keys=%s",
                    self.cloud_id,
                    missing_space_keys,
                )
                results["pages"]["errors"] += len(missing_space_keys)
                results["blogposts"]["errors"] += len(missing_space_keys)

            user_name_map = self._load_user_name_map(db)
            
            for space_key, space_id in space_id_map.items():
                page_result = await self._sync_space_pages(
                    db, space_id = space_id, space_key = space_key, since = sync_from,
                    user_name_map=user_name_map, space_name=space_name_map.get(space_key),
                    audit_context=audit_context,
                )
                results["pages"]["synced"] += page_result["synced"]
                results["pages"]["errors"] += page_result["errors"]

                blog_result = await self._sync_space_blogposts(
                    db, space_id = space_id, space_key = space_key, since = sync_from,
                    user_name_map=user_name_map, space_name=space_name_map.get(space_key),
                    audit_context=audit_context,
                )
                results["blogposts"]["synced"] += blog_result["synced"]
                results["blogposts"]["errors"] += blog_result["errors"]
            
            db.commit()

            logger.info(
                f"[CONFLUENCE][FULL SYNC] Completed : cloud_id = {self.cloud_id}, results = {results}"
            )
            return TargetSyncResult(
                synced_count=(
                    int(results["pages"]["synced"]) + int(results["blogposts"]["synced"])
                ),
                error_count=(
                    int(results["pages"]["errors"]) + int(results["blogposts"]["errors"])
                ),
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[CONFLUENCE][FULL SYNC] Failed: cloud_id={self.cloud_id}, error={e}")
            raise
        
    async def _sync_space_pages(
            self,
            db: Session,
            space_id: str,
            space_key: str,
            since: datetime | None = None,
            user_name_map: dict[str, str | None] | None = None,
            space_name: str | None = None,
            audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int]:

        results = {"synced": 0, "errors": 0}
        _ = db

        try:
            should_stop = False
            async for batch in self.client.iter_pages(
                space_id=space_id, body_format="storage",
            ):
                for raw_page in batch:
                    try:
                        page = ConfluencePageResponse.model_validate(raw_page)

                        modified_at = parse_atlassian_datetime(
                            page.version.created_at if page.version else None
                        )
                        if since and modified_at and modified_at < since:
                            should_stop = True
                            continue

                        transform_result = await self._process_page(
                            page, space_key=space_key, space_name=space_name, user_name_map=user_name_map,
                        )
                        await self._store_transform_result(
                            entity_type="page",
                            content_id=page.id,
                            space_key=space_key,
                            transform_result=transform_result,
                            audit_context=audit_context,
                        )

                        results["synced"] += 1

                    except Exception as e:
                        logger.error(
                            f"[CONFLUENCE][SYNC] Failed to process page: "
                            f"space_key={space_key}, page_id={raw_page.get('id')}, error={e}"
                        )
                        results["errors"] += 1
                if should_stop:
                    break

            logger.info(
                f"[CONFLUENCE][SYNC] Pages completed: "
                f"space_key={space_key}, synced={results['synced']}, errors={results['errors']}"
            )

        except Exception as e:
            logger.error(
                f"[CONFLUENCE][SYNC] Page sync failed: space_key={space_key}, error={e}"
            )
            results["errors"] += 1

        return results
    
    async def _sync_space_blogposts(
            self,
            db: Session,
            space_id: str,
            space_key: str,
            since: datetime | None = None,
            user_name_map: dict[str, str | None] | None = None,
            space_name: str | None = None,
            audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int]:
        
        results = {"synced": 0, "errors": 0}
        _ = db

        try:
            should_stop = False
            async for batch in self.client.iter_blogposts(
                space_id = space_id, body_format="storage",
            ):
                for raw_blogpost in batch:
                    try:
                        blogpost = ConfluenceBlogPostResponse.model_validate(raw_blogpost)

                        modified_at = parse_atlassian_datetime(
                            blogpost.version.created_at if blogpost.version else None
                        )
                        if since and modified_at and modified_at < since:
                            should_stop = True
                            continue

                        transform_result = await self._process_blogpost(
                            blogpost, space_key = space_key, space_name=space_name, user_name_map=user_name_map,
                        )
                        await self._store_transform_result(
                            entity_type="blogpost",
                            content_id=blogpost.id,
                            space_key=space_key,
                            transform_result=transform_result,
                            audit_context=audit_context,
                        )
                        
                        results["synced"] += 1

                    except Exception as e:
                        logger.error(
                            f"[CONFLUENCE][SYNC] Failed to process blogpost: "
                            f"space_key = {space_key}, blogpost_id = {raw_blogpost.get('id')}, error = {e}"
                        )
                        results["errors"] += 1
                if should_stop:
                    break

            logger.info(
                f"[CONFLUENCE][SYNC] Blogposts completed: "
                f"space_key={space_key}, synced={results['synced']}, errors={results['errors']}"
            )

        except Exception as e:
            logger.error(
                f"[CONFLUENCE][SYNC] Blogpost sync failed: space_key={space_key}, error={e}"
            )
            results["errors"] += 1
        
        return results
           

    async def _process_page(
            self,
            page: ConfluencePageResponse,
            space_key: str,
            space_name: str | None = None,
            user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
        
        footer_comments, inline_comments, labels, attachments = await self._fetch_supplementary(
            content_type="pages", content_id = page.id,
        )

        attachment_images = await self._download_images(page.id, attachments)

        return self.transformer.transform_page(
            page,
            space_key = space_key,
            space_name = space_name,
            labels=labels,
            footer_comments=footer_comments,
            inline_comments=inline_comments,
            attachment_images=attachment_images,
            site_url = self.site_url,
            user_name_map=user_name_map,
        )
    
    async def _process_blogpost(
        self,
        blogpost: ConfluenceBlogPostResponse,
        space_key: str,
        space_name: str | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:

        footer_comments, _, labels, attachments = await self._fetch_supplementary(
            content_type="blogposts", content_id=blogpost.id,
        )

        attachment_images = await self._download_images(blogpost.id, attachments)

        return self.transformer.transform_blogpost(
            blogpost,
            space_key=space_key,
            space_name=space_name,
            labels=labels,
            footer_comments=footer_comments,
            attachment_images=attachment_images,
            site_url=self.site_url,
            user_name_map=user_name_map,
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

        expected_page_ids = await self._collect_page_ids(
            space_id=space_id,
            since=since,
        )
        expected_blogpost_ids = await self._collect_blogpost_ids(
            space_id=space_id,
            since=since,
        )
        stored_page_ids = await self.repository.list_confluence_record_ids(
            space_key=space_key,
            entity_type="page",
            since=since,
        )
        stored_blogpost_ids = await self.repository.list_confluence_record_ids(
            space_key=space_key,
            entity_type="blogpost",
            since=since,
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

        space_id, space_name, user_name_map = await self._load_space_context(space_key)
        _ = space_id

        if requested_page_ids:
            failed_page_ids: list[str] = []
            succeeded_page_count = 0

            for page_id in requested_page_ids:
                try:
                    raw_page = await self.client.get_page_by_id(page_id, body_format="storage")
                    page = ConfluencePageResponse.model_validate(raw_page)
                    transform_result = await self._process_page(
                        page,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )
                    if not transform_result.documents:
                        logger.info(
                            "[CONFLUENCE][REPAIR] Page retry produced no documents: cloud_id=%s, space_key=%s, page_id=%s",
                            self.cloud_id,
                            space_key,
                            page_id,
                        )
                        continue
                    await self._store_transform_result(
                        entity_type="page",
                        content_id=page.id,
                        space_key=space_key,
                        transform_result=transform_result,
                        audit_context=None,
                    )
                    succeeded_page_count += 1
                except Exception as exc:
                    logger.warning(
                        "[CONFLUENCE][REPAIR] Failed to retry page: cloud_id=%s, space_key=%s, page_id=%s, error=%s",
                        self.cloud_id,
                        space_key,
                        page_id,
                        exc,
                    )
                    failed_page_ids.append(page_id)

            result_items.append(
                ConfluenceRecordRetryItem(
                    record_type="page",
                    requested_ids=requested_page_ids,
                    retried_count=len(requested_page_ids),
                    succeeded_count=succeeded_page_count,
                    failed_ids=self._sort_record_ids(set(failed_page_ids)),
                )
            )

        if requested_blogpost_ids:
            failed_blogpost_ids: list[str] = []
            succeeded_blogpost_count = 0

            for blogpost_id in requested_blogpost_ids:
                try:
                    raw_blogpost = await self.client.get_blogpost_by_id(
                        blogpost_id,
                        body_format="storage",
                    )
                    blogpost = ConfluenceBlogPostResponse.model_validate(raw_blogpost)
                    transform_result = await self._process_blogpost(
                        blogpost,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )
                    if not transform_result.documents:
                        logger.info(
                            "[CONFLUENCE][REPAIR] Blogpost retry produced no documents: cloud_id=%s, space_key=%s, blogpost_id=%s",
                            self.cloud_id,
                            space_key,
                            blogpost_id,
                        )
                        continue
                    await self._store_transform_result(
                        entity_type="blogpost",
                        content_id=blogpost.id,
                        space_key=space_key,
                        transform_result=transform_result,
                        audit_context=None,
                    )
                    succeeded_blogpost_count += 1
                except Exception as exc:
                    logger.warning(
                        "[CONFLUENCE][REPAIR] Failed to retry blogpost: cloud_id=%s, space_key=%s, blogpost_id=%s, error=%s",
                        self.cloud_id,
                        space_key,
                        blogpost_id,
                        exc,
                    )
                    failed_blogpost_ids.append(blogpost_id)

            result_items.append(
                ConfluenceRecordRetryItem(
                    record_type="blogpost",
                    requested_ids=requested_blogpost_ids,
                    retried_count=len(requested_blogpost_ids),
                    succeeded_count=succeeded_blogpost_count,
                    failed_ids=self._sort_record_ids(set(failed_blogpost_ids)),
                )
            )

        gap_report = await self.build_record_gap_report(
            space_key=space_key,
            sync_days=sync_days,
            sync_from_dt=sync_from_dt,
        )
        remaining_by_type = {
            item.record_type: item.missing_ids
            for item in gap_report.records
        }

        return ConfluenceRecordRetryResult(
            records=[
                ConfluenceRecordRetryItem(
                    record_type=item.record_type,
                    requested_ids=item.requested_ids,
                    retried_count=item.retried_count,
                    succeeded_count=item.succeeded_count,
                    failed_ids=item.failed_ids,
                    remaining_missing_ids=remaining_by_type.get(item.record_type, []),
                )
                for item in result_items
            ]
        )

    async def incremental_sync(
        self,
        db: Session,
        *,
        space_key: str,
        record_type: str,
        record_id: str,
        event_kind: str,
        since: datetime | None,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int | bool]:
        normalized_record_type = record_type.strip().lower()
        normalized_event_kind = event_kind.strip().lower()

        if normalized_event_kind == "deleted":
            prefix = f"confluence:{normalized_record_type}:{record_id}:chunk:"
            await self.repository.delete_by_id_prefix(prefix)
            return {
                "synced": 1,
                "errors": 0,
                "skipped": False,
            }

        space_id_map = domain_repository.get_space_id_map(db, self.cloud_id, [space_key])
        space_name_map = domain_repository.get_space_name_map(db, self.cloud_id, [space_key])
        space_id = space_id_map.get(space_key)
        if not space_id:
            raise ValueError(f"confluence space not found: space_key={space_key}")

        user_name_map = self._load_user_name_map(db)
        if normalized_record_type == "page":
            result = await self._sync_space_pages(
                db,
                space_id=space_id,
                space_key=space_key,
                since=since,
                user_name_map=user_name_map,
                space_name=space_name_map.get(space_key),
                audit_context=audit_context,
            )
        elif normalized_record_type == "blogpost":
            result = await self._sync_space_blogposts(
                db,
                space_id=space_id,
                space_key=space_key,
                since=since,
                user_name_map=user_name_map,
                space_name=space_name_map.get(space_key),
                audit_context=audit_context,
            )
        else:
            raise ValueError(f"unsupported confluence record_type: {record_type}")

        return {
            "synced": int(result.get("synced", 0)),
            "errors": int(result.get("errors", 0)),
            "skipped": False,
        }
    
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
            f"[CONFLUENCE][USER CACHE] Loaded {len(mapping)} atlassian users for cloud_id={self.cloud_id}"
        )
        return mapping

    async def _fetch_supplementary(
            self,
            content_type: str,
            content_id: str,
    ) -> tuple[
        list[ConfluenceCommentResponse],        # footer_comments
        list[ConfluenceCommentResponse],        # inline_comments
        list[str],                              # labels
        list[ConfluenceAttachmentResponse],     # attachments
    ]:
        tasks = [
            self.client.get_content_footer_comments(content_type, content_id),
            self.client.get_content_attachments(content_type, content_id),
            self.client.get_content_labels(content_type, content_id),
        ]

        if content_type == "pages":
            tasks.append(self.client.get_content_inline_comments(content_type, content_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        footer_comments = []
        if isinstance(results[0], list):
            footer_comments = [ConfluenceCommentResponse.model_validate(r) for r in results[0]]

        attachments = []
        if isinstance(results[1], list):
            attachments = [ConfluenceAttachmentResponse.model_validate(r) for r in results[1]]

        labels = []
        if isinstance(results[2], list):
            labels = [ConfluenceLabelResponse.model_validate(r).name for r in results[2]]

        inline_comments = []
        if content_type == "pages" and len(results) > 3 and isinstance(results[3], list):
            inline_comments = [ConfluenceCommentResponse.model_validate(r) for r in results[3]]
        
        return footer_comments, inline_comments, labels, attachments
    
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

        embed_inputs = transform_result.embed_inputs
        embeddings: list[list[float] | None] = [None] * len(documents)

        text_indices = [
            index for index, embed_input in enumerate(embed_inputs)
            if not embed_input.is_multimodal
        ]
        multimodal_pairs = [
            (index, embed_inputs[index])
            for index in range(len(embed_inputs))
            if embed_inputs[index].is_multimodal
        ]

        if text_indices:
            text_docs = [documents[index] for index in text_indices]
            text_embeddings = await self.repository.generate_embeddings(
                text_docs,
                audit_context=audit_context,
                context=(
                    f"entity_type={entity_type},space_key={space_key},"
                    f"doc_count={len(text_docs)},embed_mode=text_only"
                ),
            )
            for index, embedding in zip(text_indices, text_embeddings, strict=True):
                embeddings[index] = embedding

        multimodal_fallback_indices: list[int] = []
        if multimodal_pairs:
            multimodal_inputs = [embed_input for _, embed_input in multimodal_pairs]
            try:
                multimodal_embeddings = await self.embedding_service.embed_confluence_documents(
                    multimodal_inputs
                )
            except Exception as exc:
                logger.warning(
                    "[CONFLUENCE][EMBED] Multimodal embedding failed, fallback to text: "
                    "entity_type=%s, content_id=%s, error=%s",
                    entity_type,
                    content_id,
                    exc,
                )
                multimodal_embeddings = [None] * len(multimodal_pairs)

            for (doc_index, _), embedding in zip(
                multimodal_pairs, multimodal_embeddings, strict=True
            ):
                if embedding is None:
                    multimodal_fallback_indices.append(doc_index)
                    continue
                embeddings[doc_index] = embedding

        if multimodal_fallback_indices:
            fallback_docs = [documents[index] for index in multimodal_fallback_indices]
            fallback_embeddings = await self.repository.generate_embeddings(
                fallback_docs,
                audit_context=audit_context,
                context=(
                    f"entity_type={entity_type},space_key={space_key},"
                    f"doc_count={len(fallback_docs)},embed_mode=multimodal_fallback"
                ),
            )
            for index, embedding in zip(
                multimodal_fallback_indices, fallback_embeddings, strict=True
            ):
                embeddings[index] = embedding

        logger.info(
            "[CONFLUENCE][EMBED] entity_type=%s, content_id=%s, multimodal_chunks=%s, "
            "text_only_chunks=%s, skipped_images=%s, multimodal_fallback_chunks=%s",
            entity_type,
            content_id,
            len(multimodal_pairs),
            len(text_indices),
            transform_result.skipped_images,
            len(multimodal_fallback_indices),
        )

        missing_embeddings = [
            index for index, embedding in enumerate(embeddings) if embedding is None
        ]
        if missing_embeddings:
            raise RuntimeError(
                "Missing confluence embeddings after multimodal processing: "
                f"content_id={content_id}, indices={missing_embeddings}"
            )

        return [embedding for embedding in embeddings if embedding is not None]

    async def _download_images(
            self,
            content_id: str,
            attachments: list[ConfluenceAttachmentResponse]
    ) -> dict[str, ConfluenceAttachmentAsset]:
        image_attachments = [
            att for att in attachments
            if att.media_type in SUPPORTED_IMAGE_TYPES
        ]

        if not image_attachments:
            return {}
        
        results: dict[str, ConfluenceAttachmentAsset] = {}

        for att in image_attachments:
            data = await self.client.download_attachment(content_id, att.id)
            if data:
                results[att.title] = ConfluenceAttachmentAsset(
                    data=data,
                    media_type=att.media_type or "application/octet-stream",
                )
        
        return results
