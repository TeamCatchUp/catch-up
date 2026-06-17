from __future__ import annotations

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncIngestionAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncFetchResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncPersistResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncSummaryResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncTransformResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_document_builder import (
    ChannelTalkUserChatV2DocumentBuilder,
)
from catchup.sync.ingestion.schemas import SyncWindow


class ChannelTalkUserChatV2BackfillAdapter(ChannelTalkUserChatFullSyncIngestionAdapter):
    """Backfill Channel Talk UserChat v2 rows by hydrating v1 seeds through API."""

    def __init__(
        self,
        *,
        fetcher: ChannelTalkUserChatFullSyncFetcher | None = None,
        vector_store: VectorStore | None = None,
        v2_document_builder: ChannelTalkUserChatV2DocumentBuilder | None = None,
    ) -> None:
        super().__init__(
            enable_summarization=False,
            enable_v2_dual_write=True,
            vector_store=vector_store,
            v2_document_builder=v2_document_builder,
        )
        self._fetcher = fetcher

    async def fetch(
        self,
        *,
        execution: ChannelTalkUserChatV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> ChannelTalkUserChatFullSyncFetchResult:
        connection = await self._load_connection(execution=execution)
        fetcher = self._get_fetcher()
        managers_by_id = await fetcher.fetch_managers_by_id(connection=connection)
        bundles = []
        failed_record_ids = []

        for seed in execution.seeds:
            try:
                bundles.append(
                    await fetcher.fetch_user_chat_bundle_by_id(
                        connection=connection,
                        user_chat_id=seed.record_id,
                    )
                )
            except Exception:
                failed_record_ids.append(seed.record_id)

        return ChannelTalkUserChatFullSyncFetchResult(
            states=tuple(dict.fromkeys(bundle.state for bundle in bundles))
            or self._default_fetch_states(),
            sync_window=sync_window,
            bundles=tuple(bundles),
            managers_by_id=managers_by_id,
            fetched_record_ids=tuple(bundle.detail.user_chat_id for bundle in bundles),
            failed_record_ids=tuple(dict.fromkeys(failed_record_ids)),
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkUserChatV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkUserChatFullSyncFetchResult,
    ) -> ChannelTalkUserChatFullSyncTransformResult:
        _ = sync_window
        seed_by_user_chat_id = _seed_by_record_id(execution.seeds)
        documents, _document_ids, build_failed_record_ids = (
            self._v2_document_builder.build_from_backfill_seeds(
                channel_id=execution.channel_id,
                bundles=fetched.bundles,
                seed_by_user_chat_id=seed_by_user_chat_id,
                managers_by_id=fetched.managers_by_id,
            )
        )
        failed_ids = _dedupe(
            (
                *_langchain_ids_for_record_ids(
                    execution.seeds,
                    fetched.failed_record_ids,
                ),
                *_langchain_ids_for_record_ids(
                    execution.seeds,
                    build_failed_record_ids,
                ),
            )
        )
        return ChannelTalkUserChatFullSyncTransformResult(
            v2_documents=tuple(documents),
            v2_failed_ids=failed_ids,
            documents=(),
        )

    async def summarize(
        self,
        *,
        execution: ChannelTalkUserChatV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
    ) -> ChannelTalkUserChatFullSyncSummaryResult:
        _ = execution
        _ = sync_window
        return ChannelTalkUserChatFullSyncSummaryResult(
            summary_applied=False,
            document_count=len(transformed.v2_documents),
            v2_documents=transformed.v2_documents,
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkUserChatV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
        summary: ChannelTalkUserChatFullSyncSummaryResult,
    ) -> ChannelTalkUserChatFullSyncPersistResult:
        _ = sync_window
        _ = transformed
        document_ids = [str(document.id) for document in summary.v2_documents]
        if not document_ids:
            return ChannelTalkUserChatFullSyncPersistResult(
                v2_error_count=len(transformed.v2_failed_ids),
                v2_failed_ids=transformed.v2_failed_ids,
            )

        vector_store = await self._get_vector_store()
        if vector_store is None:
            v2_failed_ids = _dedupe((*transformed.v2_failed_ids, *document_ids))
            return ChannelTalkUserChatFullSyncPersistResult(
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
            v2_failed_ids = _dedupe((*transformed.v2_failed_ids, *document_ids))
            return ChannelTalkUserChatFullSyncPersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        persisted_id_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        write_failed_ids = tuple(
            document_id for document_id in document_ids if document_id not in persisted_id_set
        )
        v2_failed_ids = _dedupe((*transformed.v2_failed_ids, *write_failed_ids))
        return ChannelTalkUserChatFullSyncPersistResult(
            persisted_count=len(document_ids) - len(write_failed_ids),
            persisted_ids=tuple(document_id for document_id in document_ids if document_id not in write_failed_ids),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
        )

    def build_result(
        self,
        *,
        execution: ChannelTalkUserChatV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkUserChatFullSyncFetchResult,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
        summary: ChannelTalkUserChatFullSyncSummaryResult,
        persisted: ChannelTalkUserChatFullSyncPersistResult,
    ) -> ChannelTalkUserChatSyncExecutionResult:
        _ = sync_window
        failed_ids = _dedupe((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        return ChannelTalkUserChatSyncExecutionResult(
            tenant_id=execution.tenant_id,
            target="user_chat_v2_backfill",
            collected_count=len(fetched.fetched_record_ids),
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
                "record_type": "user_chat",
                "channel_id": execution.channel_id,
                "requested_count": len(execution.seeds),
                "failed_ids": list(failed_ids),
                "failed_record_ids": list(fetched.failed_record_ids),
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


def _seed_by_record_id(
    seeds: tuple[ChannelTalkUserChatV2BackfillSeed, ...],
) -> dict[str, ChannelTalkUserChatV2BackfillSeed]:
    return {seed.record_id: seed for seed in seeds}


def _seed_by_langchain_id(
    seeds: tuple[ChannelTalkUserChatV2BackfillSeed, ...],
) -> dict[str, ChannelTalkUserChatV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}


def _langchain_ids_for_record_ids(
    seeds: tuple[ChannelTalkUserChatV2BackfillSeed, ...],
    record_ids: tuple[str, ...],
) -> tuple[str, ...]:
    seeds_by_record_id = _seed_by_record_id(seeds)
    return tuple(
        seeds_by_record_id[record_id].langchain_id
        if record_id in seeds_by_record_id
        else record_id
        for record_id in record_ids
    )


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
