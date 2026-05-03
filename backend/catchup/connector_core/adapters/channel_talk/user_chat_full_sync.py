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
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkFetchedUserChatsResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncCheckpoint,
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
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatSyncExecutionResult,
)
from catchup.connectors.channel_talk.core.user_chat_transformer import (
    UserChatTransformer,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState


class ChannelTalkUserChatFullSyncIngestionAdapter:
    """Channel Talk UserChat sweep/list ingestion adapter."""

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
        execution: ChannelTalkUserChatSyncExecutionRequest,
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
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
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


ChannelTalkUserChatFullSyncAdapter = ChannelTalkUserChatFullSyncIngestionAdapter
