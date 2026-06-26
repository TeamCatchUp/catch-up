from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_knowledge_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import V2KnowledgeRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkFetchedUserChatsResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncCheckpoint,
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
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_document_builder import (
    ChannelTalkUserChatV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.channel_talk_user_chat import (
    UserChatTransformer,
)
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.dual_write import apply_page_content_to_vector_content
from catchup.sync.ingestion.schemas import SyncWindow


class ChannelTalkUserChatFullSyncIngestionAdapter:
    """Channel Talk UserChat sweep/list ingestion adapter."""

    def __init__(
        self,
        *,
        enable_summarization: bool = True,
        enable_v2_dual_write: bool = False,
        max_user_chat_pages_per_run: int | None = None,
        user_chat_list_limit: int | None = None,
        vector_store: VectorStore | None = None,
        v2_knowledge_repository: V2KnowledgeRepository | None = None,
        v2_document_builder: ChannelTalkUserChatV2DocumentBuilder | None = None,
    ) -> None:
        self._fetcher: ChannelTalkUserChatFullSyncFetcher | None = None
        self._document_builder = UserChatTransformer()
        self._v2_document_builder = (
            v2_document_builder or ChannelTalkUserChatV2DocumentBuilder()
        )
        self._enable_summarization = enable_summarization
        self._enable_v2_dual_write = enable_v2_dual_write
        self._max_user_chat_pages_per_run = max_user_chat_pages_per_run
        self._user_chat_list_limit = user_chat_list_limit
        self._summarizer: SummarizerService | None = None
        self._repository: PGVectorRepository | None = None
        self._vector_store = vector_store
        self._v2_knowledge_repository = v2_knowledge_repository

    async def fetch(
        self,
        *,
        execution: ChannelTalkUserChatSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> ChannelTalkUserChatFullSyncFetchResult:
        fetch_states = self._default_fetch_states()
        checkpoint = execution.checkpoint
        self._validate_checkpoint_window(
            execution=execution,
            sync_window=sync_window,
            fetch_states=fetch_states,
        )
        connection = await self._load_connection(execution=execution)
        fetcher = self._get_fetcher()
        managers_by_id = await fetcher.fetch_managers_by_id(
            connection=connection,
        )
        fetched_user_chats = await fetcher.fetch_user_chats(
            connection=connection,
            states=fetch_states,
            sync_window=sync_window,
            checkpoint_state=checkpoint.state if checkpoint is not None else None,
            checkpoint_cursor=checkpoint.next_cursor
            if checkpoint is not None
            else None,
        )
        return ChannelTalkUserChatFullSyncFetchResult(
            states=fetch_states,
            sync_window=sync_window,
            bundles=fetched_user_chats.bundles,
            managers_by_id=managers_by_id,
            fetched_record_ids=tuple(
                bundle.detail.user_chat_id for bundle in fetched_user_chats.bundles
            ),
            next_checkpoint=self._build_next_checkpoint(
                execution=execution,
                sync_window=sync_window,
                fetched_user_chats=fetched_user_chats,
            ),
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkUserChatSyncExecutionRequest,
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
        execution: ChannelTalkUserChatSyncExecutionRequest,
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
        execution: ChannelTalkUserChatSyncExecutionRequest,
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
        execution: ChannelTalkUserChatSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: ChannelTalkUserChatFullSyncFetchResult,
        transformed: ChannelTalkUserChatFullSyncTransformResult,
        summary: ChannelTalkUserChatFullSyncSummaryResult,
        persisted: ChannelTalkUserChatFullSyncPersistResult,
    ) -> ChannelTalkUserChatSyncExecutionResult:
        _ = sync_window
        return ChannelTalkUserChatSyncExecutionResult(
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

    @staticmethod
    def _validate_checkpoint_window(
        *,
        execution: ChannelTalkUserChatSyncExecutionRequest,
        sync_window: SyncWindow,
        fetch_states: tuple[ChannelTalkUserChatState, ...],
    ) -> None:
        if execution.checkpoint is None:
            return
        if execution.checkpoint.state not in fetch_states:
            raise ValueError("checkpoint.state must be included in fetch states")
        if execution.checkpoint.window != sync_window:
            raise ValueError("checkpoint.window must match sync_window")

    @staticmethod
    def _default_fetch_states() -> tuple[ChannelTalkUserChatState, ...]:
        """Current UserChat list sweep policy for the Channel Talk full-sync lane."""

        return (
            ChannelTalkUserChatState.OPENED,
            ChannelTalkUserChatState.CLOSED,
            ChannelTalkUserChatState.SNOOZED,
        )

    @staticmethod
    def _build_next_checkpoint(
        *,
        execution: ChannelTalkUserChatSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched_user_chats: ChannelTalkFetchedUserChatsResult,
    ) -> ChannelTalkUserChatFullSyncCheckpoint | None:
        if fetched_user_chats.next_checkpoint_state is None:
            return None
        return ChannelTalkUserChatFullSyncCheckpoint(
            tenant_id=execution.tenant_id,
            state=fetched_user_chats.next_checkpoint_state,
            window=sync_window,
            next_cursor=fetched_user_chats.next_checkpoint_cursor,
        )

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

    def _get_v2_knowledge_repository(self) -> V2KnowledgeRepository | None:
        if not self._enable_v2_dual_write:
            return None
        if self._v2_knowledge_repository is None:
            self._v2_knowledge_repository = get_v2_knowledge_repository()
        return self._v2_knowledge_repository

    def _get_fetcher(self) -> ChannelTalkUserChatFullSyncFetcher:
        if self._fetcher is None:
            self._fetcher = ChannelTalkUserChatFullSyncFetcher(
                max_user_chat_pages_per_run=self._max_user_chat_pages_per_run,
                user_chat_list_limit=self._user_chat_list_limit,
            )
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


ChannelTalkUserChatFullSyncAdapter = ChannelTalkUserChatFullSyncIngestionAdapter
