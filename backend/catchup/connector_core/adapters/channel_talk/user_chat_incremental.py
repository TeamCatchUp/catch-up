from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncFetchResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncPersistResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncSummaryResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncTransformResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatIncrementalExecutionRequest,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatIncrementalExecutionResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.connectors.channel_talk.core.user_chat_transformer import (
    UserChatTransformer,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow


class ChannelTalkUserChatIncrementalIngestionAdapter:
    """Exact-refresh ingestion adapter for Channel Talk UserChat records."""

    def __init__(
        self,
        *,
        enable_summarization: bool = True,
    ) -> None:
        self._fetcher: ChannelTalkUserChatFullSyncFetcher | None = None
        self._document_builder = UserChatTransformer()
        self._enable_summarization = enable_summarization
        self._summarizer: SummarizerService | None = None
        self._repository: PGVectorRepository | None = None

    async def fetch(
        self,
        *,
        execution: ChannelTalkUserChatIncrementalExecutionRequest,
        sync_window: SyncWindow,
    ) -> ChannelTalkUserChatFullSyncFetchResult:
        connection = await self._load_connection(execution=execution)
        fetcher = self._get_fetcher()
        managers_by_id = await fetcher.fetch_managers_by_id(
            connection=connection,
        )
        bundle = await fetcher.fetch_user_chat_bundle_by_id(
            connection=connection,
            user_chat_id=execution.user_chat_id,
        )
        return ChannelTalkUserChatFullSyncFetchResult(
            states=(bundle.state,),
            sync_window=sync_window,
            bundles=(bundle,),
            managers_by_id=managers_by_id,
            fetched_record_ids=(bundle.detail.user_chat_id,),
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkUserChatIncrementalExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkUserChatFullSyncFetchResult,
    ) -> ChannelTalkUserChatFullSyncTransformResult:
        return ChannelTalkUserChatFullSyncTransformResult(
            documents=tuple(
                self._document_builder.build(
                    execution=execution,
                    sync_window=sync_window,
                    bundle=bundle,
                    managers_by_id=fetched.managers_by_id,
                )
                for bundle in fetched.bundles
            )
        )

    async def summarize(
        self,
        *,
        execution: ChannelTalkUserChatIncrementalExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
    ) -> ChannelTalkUserChatFullSyncSummaryResult:
        _ = sync_window
        documents = transformed.documents
        included_message_count = sum(
            document.logical_metadata.user_chat_core.messages.included_message_count
            for document in documents
        )
        excluded_message_count = sum(
            document.logical_metadata.user_chat_core.messages.excluded_message_count
            for document in documents
        )
        if not self._enable_summarization or not documents:
            return ChannelTalkUserChatFullSyncSummaryResult(
                summary_applied=False,
                document_count=len(documents),
                included_message_count=included_message_count,
                excluded_message_count=excluded_message_count,
            )

        requests = [
            SummarizeRequest(
                content=document.contextual_content,
                source_type="channel_talk_user_chat",
            )
            for document in documents
        ]
        summarized = await self._get_summarizer().summarize_batch(
            requests,
            audit_context=execution.audit_context,
            context=(
                "entity_type=user_chat,"
                f"channel_id={execution.channel_id},"
                f"doc_count={len(documents)}"
            ),
        )
        for document, summary in zip(documents, summarized):
            document.page_content = summary

        return ChannelTalkUserChatFullSyncSummaryResult(
            summary_applied=bool(documents),
            document_count=len(documents),
            included_message_count=included_message_count,
            excluded_message_count=excluded_message_count,
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkUserChatIncrementalExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
        summary: ChannelTalkUserChatFullSyncSummaryResult,
    ) -> ChannelTalkUserChatFullSyncPersistResult:
        _ = execution
        _ = sync_window
        _ = summary
        repository = await self._get_repository()
        documents = [
            Document(
                id=document.document_id,
                page_content=document.page_content,
                metadata=document.storage_metadata,
            )
            for document in transformed.documents
        ]
        document_ids = [document.document_id for document in transformed.documents]
        persisted_ids = await repository.add_documents(documents, ids=document_ids)
        return ChannelTalkUserChatFullSyncPersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
        )

    def build_result(
        self,
        *,
        execution: ChannelTalkUserChatIncrementalExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkUserChatFullSyncFetchResult,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
        summary: ChannelTalkUserChatFullSyncSummaryResult,
        persisted: ChannelTalkUserChatFullSyncPersistResult,
    ) -> ChannelTalkUserChatIncrementalExecutionResult:
        _ = sync_window
        return ChannelTalkUserChatIncrementalExecutionResult(
            tenant_id=execution.tenant_id,
            collected_count=len(fetched.fetched_record_ids),
            document_count=len(transformed.documents),
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
        )

    async def sync_user_chat_by_id(
        self,
        *,
        execution: ChannelTalkUserChatSyncExecutionRequest,
        user_chat_id: str,
        sync_window: SyncWindow,
    ) -> ChannelTalkUserChatFullSyncPersistResult:
        incremental_execution = ChannelTalkUserChatIncrementalExecutionRequest(
            tenant_id=execution.tenant_id,
            checkpoint=execution.checkpoint,
            audit_context=execution.audit_context,
            user_chat_id=user_chat_id,
        )
        result = await run_sync_ingestion(
            port=self,
            execution=incremental_execution,
            sync_window=sync_window,
        )
        return result.persisted

    async def _load_connection(
        self,
        *,
        execution: ChannelTalkUserChatSyncExecutionRequest,
    ) -> ChannelTalkUserChatFullSyncConnection:
        connection = await run_in_threadpool(
            load_channel_talk_connection,
            execution.channel_id,
        )
        if connection is None:
            raise ValueError("channel_talk is not connected")
        if connection.channel_id != execution.channel_id:
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel"
            )
        return ChannelTalkUserChatFullSyncConnection.from_credentials_record(connection)

    async def _get_repository(self) -> PGVectorRepository:
        if self._repository is None:
            repository = self._build_repository()
            try:
                repository.ensure_initialized()
            except RuntimeError:
                await repository.initialize(None)
            self._repository = repository
        assert self._repository is not None
        return self._repository

    def _get_fetcher(self) -> ChannelTalkUserChatFullSyncFetcher:
        if self._fetcher is None:
            self._fetcher = ChannelTalkUserChatFullSyncFetcher()
        return self._fetcher

    def _get_summarizer(self) -> SummarizerService:
        if self._summarizer is None:
            self._summarizer = get_summarizer_service()
        return self._summarizer

    @staticmethod
    def _build_repository() -> PGVectorRepository:
        return get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )


ChannelTalkUserChatIncrementalAdapter = ChannelTalkUserChatIncrementalIngestionAdapter
