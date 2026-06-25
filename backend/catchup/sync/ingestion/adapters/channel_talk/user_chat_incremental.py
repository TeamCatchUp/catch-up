from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncConnection,
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
    ChannelTalkUserChatIncrementalExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatIncrementalExecutionResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_document_builder import (
    ChannelTalkUserChatV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.channel_talk_user_chat import (
    UserChatTransformer,
)
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.dual_write import apply_page_content_to_vector_content
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow


class ChannelTalkUserChatIncrementalIngestionAdapter:
    """Exact-refresh ingestion adapter for Channel Talk UserChat records."""

    def __init__(
        self,
        *,
        enable_summarization: bool = True,
        enable_v2_dual_write: bool = False,
        vector_store: VectorStore | None = None,
        v2_document_builder: ChannelTalkUserChatV2DocumentBuilder | None = None,
    ) -> None:
        self._fetcher: ChannelTalkUserChatFullSyncFetcher | None = None
        self._document_builder = UserChatTransformer()
        self._v2_document_builder = (
            v2_document_builder or ChannelTalkUserChatV2DocumentBuilder()
        )
        self._enable_summarization = enable_summarization
        self._enable_v2_dual_write = enable_v2_dual_write
        self._summarizer: SummarizerService | None = None
        self._repository: PGVectorRepository | None = None
        self._vector_store = vector_store

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
        documents = tuple(
            self._document_builder.build(
                execution=execution,
                sync_window=sync_window,
                bundle=bundle,
                managers_by_id=fetched.managers_by_id,
            )
            for bundle in fetched.bundles
        )
        v2_documents = []
        v2_failed_ids: tuple[str, ...] = ()
        if self._enable_v2_dual_write:
            v2_documents, v2_failed_ids = (
                self._v2_document_builder.build_from_prepared_documents(
                    channel_id=execution.channel_id,
                    bundles=fetched.bundles,
                    prepared_documents=documents,
                    managers_by_id=fetched.managers_by_id,
                )
            )
        return ChannelTalkUserChatFullSyncTransformResult(
            documents=documents,
            v2_documents=tuple(v2_documents),
            v2_failed_ids=v2_failed_ids,
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
                v2_documents=transformed.v2_documents,
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

        v2_documents = self._apply_v1_page_content_to_v2_content(
            v1_documents=self._to_langchain_documents(documents),
            v2_documents=list(transformed.v2_documents),
        )
        return ChannelTalkUserChatFullSyncSummaryResult(
            summary_applied=bool(documents),
            document_count=len(documents),
            included_message_count=included_message_count,
            excluded_message_count=excluded_message_count,
            v2_documents=tuple(v2_documents),
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkUserChatIncrementalExecutionRequest,
        sync_window: SyncWindow,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
        summary: ChannelTalkUserChatFullSyncSummaryResult,
    ) -> ChannelTalkUserChatFullSyncPersistResult:
        _ = sync_window
        repository = await self._get_repository()
        documents = self._to_langchain_documents(transformed.documents)
        document_ids = [document.document_id for document in transformed.documents]
        v2_failed_ids = tuple(transformed.v2_failed_ids)

        if summary.v2_documents:
            vector_store = await self._get_vector_store()
            result = await DualWriter(
                repository=repository,
                vector_store=vector_store,
            ).upsert_documents(
                source_documents=documents,
                vector_documents=list(summary.v2_documents),
                ids=document_ids,
                audit_context=execution.audit_context,
                context=(
                    "entity_type=user_chat,"
                    f"channel_id={execution.channel_id},"
                    f"doc_count={len(documents)}"
                ),
            )
            persisted_ids = result.persisted_ids
            v2_failed_ids = tuple(
                dict.fromkeys((*v2_failed_ids, *result.vector_failed_ids))
            )
        else:
            persisted_ids = await repository.add_documents(documents, ids=document_ids)

        return ChannelTalkUserChatFullSyncPersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
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
            persisted_count=persisted.persisted_count,
            failed_count=persisted.v2_error_count,
            v2_failed_count=persisted.v2_error_count,
            v2_failed_ids=persisted.v2_failed_ids,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            metadata={
                "v2_failed_count": persisted.v2_error_count,
                "v2_failed_ids": list(persisted.v2_failed_ids),
            },
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

    async def _get_vector_store(self) -> VectorStore | None:
        if not self._enable_v2_dual_write:
            return None
        if self._vector_store is None:
            embeddings = get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
            vector_store = get_v2_vector_store(embeddings)
            await vector_store.initialize()
            self._vector_store = vector_store
        return self._vector_store

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

    @staticmethod
    def _to_langchain_documents(
        documents: tuple[object, ...],
    ) -> list[Document]:
        return [
            Document(
                id=document.document_id,
                page_content=document.page_content,
                metadata=document.storage_metadata,
            )
            for document in documents
        ]

    @staticmethod
    def _apply_v1_page_content_to_v2_content(
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
    ) -> list[Document]:
        return apply_page_content_to_vector_content(
            source_documents=v1_documents,
            vector_documents=v2_documents,
            connector="channel_talk",
            entity_type="user_chat",
            operation="channel_talk_user_chat_v2_dual_write",
        )


ChannelTalkUserChatIncrementalAdapter = ChannelTalkUserChatIncrementalIngestionAdapter
