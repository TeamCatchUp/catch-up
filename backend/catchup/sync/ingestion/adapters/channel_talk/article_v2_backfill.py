from __future__ import annotations

import structlog

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
)
from catchup.sync.ingestion.adapters.channel_talk.article_full_sync import (
    CHANNEL_TALK_ARTICLE_LANGUAGE,
)
from catchup.sync.ingestion.adapters.channel_talk.article_full_sync import (
    ChannelTalkArticleFullSyncIngestionAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncConnection,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncFetchResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncPersistResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncSummaryResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncTransformResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticlePreparedDocument,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillExecutionResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.article_v2_document_builder import (
    ChannelTalkArticleV2DocumentBuilder,
)
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class ChannelTalkArticleV2BackfillAdapter(ChannelTalkArticleFullSyncIngestionAdapter):
    """Backfill Channel Talk Article v2 rows by hydrating v1 seeds through API."""

    def __init__(
        self,
        *,
        fetcher: ChannelTalkArticleFullSyncFetcher | None = None,
        vector_store: VectorStore | None = None,
        v2_document_builder: ChannelTalkArticleV2DocumentBuilder | None = None,
    ) -> None:
        super().__init__(
            enable_v2_dual_write=True,
            vector_store=vector_store,
            v2_document_builder=v2_document_builder,
        )
        self._fetcher = fetcher

    async def fetch(
        self,
        *,
        execution: ChannelTalkArticleV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> ChannelTalkArticleFullSyncFetchResult:
        _ = sync_window
        connection = ChannelTalkArticleFullSyncConnection.from_credentials_record(
            execution.document_connection,
        )
        fetcher = self._get_fetcher()
        bundles = []
        failed_article_ids = []

        for article_id in _dedupe(tuple(seed.record_id for seed in execution.seeds)):
            try:
                bundles.append(
                    await fetcher.fetch_article_bundle_by_id(
                        connection=connection,
                        article_id=article_id,
                        language=CHANNEL_TALK_ARTICLE_LANGUAGE,
                    )
                )
            except Exception:
                failed_article_ids.append(article_id)

        return ChannelTalkArticleFullSyncFetchResult(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=CHANNEL_TALK_ARTICLE_LANGUAGE,
            bundles=tuple(bundles),
            fetched_count=len(bundles),
            fetched_article_ids=tuple(bundle.article_id for bundle in bundles),
            failed_article_ids=tuple(dict.fromkeys(failed_article_ids)),
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkArticleV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkArticleFullSyncFetchResult,
    ) -> ChannelTalkArticleFullSyncTransformResult:
        documents: list[ChannelTalkArticlePreparedDocument] = []
        delete_prefixes: list[str] = []

        for bundle in fetched.bundles:
            transformed_bundle = self._document_builder.transform(
                execution=execution,
                sync_window=sync_window,
                bundle=bundle,
            )
            documents.extend(
                ChannelTalkArticlePreparedDocument(
                    document_id=document.document_id,
                    article_id=document.article_id,
                    page_content=document.page_content,
                    chunk_body_text=document.chunk_body_text,
                    logical_metadata=document.logical_metadata,
                    storage_metadata=document.storage_metadata,
                )
                for document in transformed_bundle.documents
            )
            delete_prefixes.append(transformed_bundle.delete_prefix)

        seed_by_document_id = _seed_by_langchain_id(execution.seeds)
        v2_documents, _document_ids, build_failed_ids = (
            self._v2_document_builder.build_from_backfill_seeds(
                prepared_documents=tuple(documents),
                seed_by_document_id=seed_by_document_id,
            )
        )
        failed_ids = _dedupe(
            (
                *_langchain_ids_for_record_ids(
                    execution.seeds,
                    fetched.failed_article_ids,
                ),
                *build_failed_ids,
            )
        )
        return ChannelTalkArticleFullSyncTransformResult(
            documents=(),
            delete_prefixes=tuple(dict.fromkeys(delete_prefixes)),
            v2_documents=tuple(v2_documents),
            v2_failed_ids=failed_ids,
        )

    async def summarize(
        self,
        *,
        execution: ChannelTalkArticleV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
    ) -> ChannelTalkArticleFullSyncSummaryResult:
        _ = execution
        _ = sync_window
        return ChannelTalkArticleFullSyncSummaryResult(
            summary_applied=False,
            document_count=len(transformed.v2_documents),
            v2_documents=transformed.v2_documents,
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkArticleV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
    ) -> ChannelTalkArticleFullSyncPersistResult:
        _ = sync_window
        v2_failed_ids = transformed.v2_failed_ids
        document_ids = [str(document.id) for document in summary.v2_documents]
        if not document_ids:
            return ChannelTalkArticleFullSyncPersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        vector_store = await self._get_vector_store()
        if vector_store is None:
            v2_failed_ids = _dedupe((*v2_failed_ids, *document_ids))
            return ChannelTalkArticleFullSyncPersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        seed_by_langchain_id = _seed_by_langchain_id(execution.seeds)
        embeddings = [
            seed_by_langchain_id[document_id].embedding for document_id in document_ids
        ]
        try:
            persisted_ids = await vector_store.upsert_documents(
                list(summary.v2_documents),
                ids=document_ids,
                embeddings=embeddings,
            )
        except Exception:
            v2_failed_ids = _dedupe((*v2_failed_ids, *document_ids))
            return ChannelTalkArticleFullSyncPersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        persisted_id_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        write_failed_ids = tuple(
            document_id
            for document_id in document_ids
            if document_id not in persisted_id_set
        )
        metadata_check_ids = [
            document_id
            for document_id in document_ids
            if document_id in persisted_id_set
        ]
        metadata_failed_ids = await vector_store.find_missing_metadata_namespace_ids(
            metadata_check_ids,
            namespace="channel_talk_document_article",
        )
        if metadata_failed_ids:
            logger.warning(
                "channel_talk_document_article_v2_backfill_metadata_missing_after_persist",
                connector="channel_talk",
                entity_type="document_article",
                scope_id=execution.channel_id,
                target_id=execution.space_id,
                namespace="channel_talk_document_article",
                missing_metadata_ids=list(metadata_failed_ids),
                persisted_id_count=len(metadata_check_ids),
                missing_count=len(metadata_failed_ids),
            )
        failed_document_ids = _dedupe((*write_failed_ids, *metadata_failed_ids))
        v2_failed_ids = _dedupe((*v2_failed_ids, *failed_document_ids))
        return ChannelTalkArticleFullSyncPersistResult(
            persisted_count=len(document_ids) - len(failed_document_ids),
            persisted_ids=tuple(
                document_id
                for document_id in document_ids
                if document_id not in failed_document_ids
            ),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
        )

    def build_result(
        self,
        *,
        execution: ChannelTalkArticleV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkArticleFullSyncFetchResult,
        transformed: ChannelTalkArticleFullSyncTransformResult,
        summary: ChannelTalkArticleFullSyncSummaryResult,
        persisted: ChannelTalkArticleFullSyncPersistResult,
    ) -> ChannelTalkArticleV2BackfillExecutionResult:
        _ = sync_window
        failed_ids = _dedupe((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        return ChannelTalkArticleV2BackfillExecutionResult(
            tenant_id=execution.tenant_id,
            target="document_article_v2_backfill",
            collected_count=len(fetched.fetched_article_ids),
            document_count=len(summary.v2_documents),
            persisted_count=persisted.persisted_count,
            failed_count=len(failed_ids),
            v2_failed_count=len(failed_ids),
            v2_failed_ids=failed_ids,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            metadata={
                "record_type": "document_article",
                "channel_id": execution.channel_id,
                "space_id": execution.space_id,
                "requested_count": len(execution.seeds),
                "failed_ids": list(failed_ids),
                "failed_record_ids": list(fetched.failed_article_ids),
                "v2_failed_ids": list(failed_ids),
            },
        )

    async def _get_vector_store(self) -> VectorStore | None:
        if self._vector_store is None:
            embeddings = get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
            vector_store = get_v2_vector_store(embeddings)
            await vector_store.initialize()
            self._vector_store = vector_store
        return self._vector_store


def _seed_by_langchain_id(
    seeds: tuple[ChannelTalkArticleV2BackfillSeed, ...],
) -> dict[str, ChannelTalkArticleV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}


def _langchain_ids_for_record_ids(
    seeds: tuple[ChannelTalkArticleV2BackfillSeed, ...],
    record_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        seed.langchain_id
        for seed in seeds
        if seed.record_id in set(record_ids)
    )


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
