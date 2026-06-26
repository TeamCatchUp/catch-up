from __future__ import annotations

import structlog

from catchup.components.vector_db.v2 import V2KnowledgeRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.confluence.schemas import ConfluenceBlogPostResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceFetchResult,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpacePersistResult,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceSummaryResult,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceSyncAdapter,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceSyncDependencies,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceTransformItem,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceTransformResult,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceV2BackfillExecutionResult,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.confluence.v2_document_builder import (
    ConfluenceV2BackfillSeed as BuilderBackfillSeed,
)
from catchup.sync.ingestion.adapters.confluence.v2_document_builder import (
    ConfluenceV2DocumentBuilder,
)
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class ConfluenceV2BackfillAdapter(ConfluenceSpaceSyncAdapter):
    """Backfill Confluence page/blogpost v2 rows from v1 seed rows."""

    def __init__(
        self,
        *,
        dependencies: ConfluenceSpaceSyncDependencies,
        vector_store: VectorStore | None = None,
        v2_knowledge_repository: V2KnowledgeRepository | None = None,
        v2_document_builder: ConfluenceV2DocumentBuilder | None = None,
    ) -> None:
        super().__init__(
            dependencies=dependencies,
            enable_v2_dual_write=True,
            vector_store=vector_store,
            v2_knowledge_repository=v2_knowledge_repository,
            v2_document_builder=v2_document_builder,
        )

    async def fetch(
        self,
        *,
        execution: ConfluenceV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> ConfluenceSpaceFetchResult:
        _ = sync_window
        space_id, space_name, user_name_map = await self._space_context(
            execution.space_key
        )
        records = []
        failed_ids: list[str] = []
        for record_id in _dedupe(tuple(seed.record_id for seed in execution.seeds)):
            try:
                if execution.record_type == "page":
                    records.append(
                        await self._client.get_page_by_id(
                            record_id,
                            body_format="storage",
                        )
                    )
                else:
                    records.append(
                        await self._client.get_blogpost_by_id(
                            record_id,
                            body_format="storage",
                        )
                    )
            except Exception as exc:
                if self._is_retryable_connector_error(exc):
                    raise
                affected_ids = _seed_ids_for_record(execution.seeds, record_id)
                logger.warning(
                    "confluence_v2_backfill_record_fetch_failed",
                    connector="confluence",
                    entity_type=execution.record_type,
                    scope_id=execution.tenant_id,
                    target_id=execution.space_key,
                    record_id=record_id,
                    failed_id_count=len(affected_ids),
                    exception_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=True,
                )
                failed_ids.extend(affected_ids)
        return ConfluenceSpaceFetchResult(
            requested_count=len(execution.seeds),
            records=tuple(records),
            record_type=execution.record_type,
            space_id=space_id,
            space_key=execution.space_key,
            space_name=execution.space_name or space_name,
            user_name_map=user_name_map,
            is_last=True,
            checkpoint=None,
            v2_failed_ids=_dedupe(tuple(failed_ids)),
        )

    async def transform(
        self,
        *,
        execution: ConfluenceV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: ConfluenceSpaceFetchResult,
    ) -> ConfluenceSpaceTransformResult:
        _ = sync_window
        items: list[ConfluenceSpaceTransformItem] = []
        failed_ids = tuple(fetched.v2_failed_ids)
        space_key = fetched.space_key or execution.space_key
        space_name = fetched.space_name or execution.space_name
        user_name_map = fetched.user_name_map
        for raw_content in fetched.records:
            content_id = _raw_content_record_id(raw_content)
            try:
                if execution.record_type == "page":
                    content = ConfluencePageResponse.model_validate(raw_content)
                    content_id = content.id
                    transform_result = await self._process_page(
                        content,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )
                else:
                    content = ConfluenceBlogPostResponse.model_validate(raw_content)
                    content_id = content.id
                    transform_result = await self._process_blogpost(
                        content,
                        space_key=space_key,
                        space_name=space_name,
                        user_name_map=user_name_map,
                    )
                items.append(
                    ConfluenceSpaceTransformItem(
                        content_id=content.id,
                        transform_result=transform_result,
                    )
                )
            except Exception as exc:
                if self._is_retryable_connector_error(exc):
                    raise
                affected_ids = _seed_ids_for_record(execution.seeds, content_id)
                logger.warning(
                    "confluence_v2_backfill_record_transform_failed",
                    connector="confluence",
                    entity_type=execution.record_type,
                    scope_id=execution.tenant_id,
                    target_id=execution.space_key,
                    record_id=content_id,
                    failed_id_count=len(affected_ids),
                    exception_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=True,
                )
                failed_ids = _dedupe((*failed_ids, *affected_ids))

        seed_by_langchain_id = _seed_by_langchain_id(execution.seeds)
        prepared_chunks = tuple(
            prepared
            for item in items
            for prepared in item.transform_result.v2_prepared_chunks
        )
        v2_documents, _document_ids, build_failed_ids = (
            self._v2_document_builder.build_from_backfill_seeds(
                cloud_id=self._cloud_id,
                prepared_chunks=prepared_chunks,
                seed_by_langchain_id={
                    langchain_id: BuilderBackfillSeed(
                        langchain_id=seed.langchain_id,
                        content=seed.content,
                        record_id=seed.record_id,
                    )
                    for langchain_id, seed in seed_by_langchain_id.items()
                },
            )
        )
        return ConfluenceSpaceTransformResult(
            requested_count=len(execution.seeds),
            record_type=execution.record_type,
            items=tuple(items),
            space_key=space_key,
            space_name=space_name,
            v2_documents=tuple(v2_documents),
            v2_failed_ids=_dedupe((*failed_ids, *build_failed_ids)),
        )

    async def persist(
        self,
        *,
        execution: ConfluenceV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: ConfluenceSpaceTransformResult,
        summary: ConfluenceSpaceSummaryResult,
    ) -> ConfluenceSpacePersistResult:
        _ = sync_window, summary
        v2_failed_ids = tuple(transformed.v2_failed_ids)
        documents = list(transformed.v2_documents)
        if not documents:
            return ConfluenceSpacePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        vector_store = await self._get_vector_store()
        if vector_store is None:
            v2_failed_ids = _dedupe((*v2_failed_ids, *self._document_ids(tuple(documents))))
            return ConfluenceSpacePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        seed_by_id = _seed_by_langchain_id(execution.seeds)
        document_ids = [str(document.id) for document in documents]
        embeddings = [seed_by_id[document_id].embedding for document_id in document_ids]
        try:
            persisted_ids = await vector_store.upsert_documents(
                documents,
                ids=document_ids,
                embeddings=embeddings,
            )
        except Exception:
            v2_failed_ids = _dedupe((*v2_failed_ids, *document_ids))
            return ConfluenceSpacePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        persisted_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        write_failed_ids = tuple(
            document_id for document_id in document_ids if document_id not in persisted_set
        )
        metadata_check_ids = [
            document_id
            for document_id in document_ids
            if document_id in persisted_set
        ]
        namespace = f"confluence_{execution.record_type}"
        v2_knowledge_repository = self._get_v2_knowledge_repository()
        if v2_knowledge_repository is None:
            metadata_failed_ids = tuple(metadata_check_ids)
        else:
            metadata_failed_ids = (
                await v2_knowledge_repository.find_missing_metadata_namespace_ids(
                    metadata_check_ids,
                    namespace=namespace,
                )
            )
        if metadata_failed_ids:
            logger.warning(
                "confluence_v2_backfill_metadata_missing_after_persist",
                connector="confluence",
                entity_type=execution.record_type,
                scope_id=execution.tenant_id,
                target_id=execution.space_key,
                namespace=namespace,
                missing_metadata_ids=list(metadata_failed_ids),
                persisted_id_count=len(metadata_check_ids),
                missing_count=len(metadata_failed_ids),
            )
        failed_document_ids = _dedupe((*write_failed_ids, *metadata_failed_ids))
        v2_failed_ids = _dedupe((*v2_failed_ids, *failed_document_ids))
        return ConfluenceSpacePersistResult(
            persisted_count=len(document_ids) - len(failed_document_ids),
            error_count=len(failed_document_ids),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
        )

    def build_result(
        self,
        *,
        execution: ConfluenceV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: ConfluenceSpaceFetchResult,
        transformed: ConfluenceSpaceTransformResult,
        summary: ConfluenceSpaceSummaryResult,
        persisted: ConfluenceSpacePersistResult,
    ) -> ConfluenceV2BackfillExecutionResult:
        _ = sync_window, summary
        failed_ids = _dedupe((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        return ConfluenceV2BackfillExecutionResult(
            tenant_id=execution.tenant_id,
            persisted_count=persisted.persisted_count,
            failed_count=persisted.error_count,
            v2_failed_count=len(failed_ids),
            v2_failed_ids=failed_ids,
            skipped=not persisted.persisted_count and not failed_ids,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            record_type=execution.record_type,
            seeds_count=len(execution.seeds),
            metadata={
                "v2_failed_count": len(failed_ids),
                "v2_failed_ids": list(failed_ids),
            },
        )


def _seed_by_langchain_id(
    seeds: tuple[ConfluenceV2BackfillSeed, ...],
) -> dict[str, ConfluenceV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}


def _seed_ids_for_record(
    seeds: tuple[ConfluenceV2BackfillSeed, ...],
    record_id: str | None,
) -> tuple[str, ...]:
    if not record_id:
        return ()
    return tuple(seed.langchain_id for seed in seeds if seed.record_id == record_id)


def _raw_content_record_id(raw_content: object) -> str | None:
    if isinstance(raw_content, dict):
        value = raw_content.get("id")
    else:
        value = getattr(raw_content, "id", None)
    if value is None:
        return None
    return str(value)


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
