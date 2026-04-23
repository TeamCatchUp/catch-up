from __future__ import annotations

from typing import Literal

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.connector_core.document_format import ChannelTalkUserChatAnchorsMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatAssignmentMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatChatMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatChunkMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatCoreMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatCustomerMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatLogicalMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatMessageMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatMetricsMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatTagsMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatTimingMetadata
from catchup.connector_core.document_format import DocumentBaseMetadata
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.full_sync import FullSyncExecutionRequest
from catchup.connector_core.ports.full_sync import FullSyncExecutionResult
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.full_sync_fetcher import ChannelTalkFetchedUserChat
from catchup.connectors.channel_talk.full_sync_fetcher import (
    ChannelTalkFetchedUserChatsResult,
)
from catchup.connectors.channel_talk.full_sync_fetcher import ChannelTalkFullSyncFetcher
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessage
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessageAttachment
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessageButton
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessageForm
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessageLog
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessageWebPage
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas import ChannelTalkUserFoundation
from catchup.sync.audit import SyncAuditContext
from catchup.utils.validation import require_text


class ChannelTalkFullSyncCheckpoint(BaseModel):
    """Adapter-local resume shape for the current Channel Talk full-sync lane."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    target: Literal["user_chat"] = "user_chat"
    state: ChannelTalkUserChatState
    window: FullSyncWindow
    next_cursor: str | None = None

    @field_validator("tenant_id")
    @classmethod
    def _validate_tenant_id(cls, value: str) -> str:
        return require_text(value, "tenant_id")


class ChannelTalkFullSyncExecutionRequest(FullSyncExecutionRequest):
    """Target-oriented execution request for the current Channel Talk full-sync lane."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["user_chat"] = "user_chat"
    checkpoint: ChannelTalkFullSyncCheckpoint | None = None
    audit_context: SyncAuditContext | None = None

    @model_validator(mode="after")
    def _validate_checkpoint_alignment(
        self,
    ) -> "ChannelTalkFullSyncExecutionRequest":
        if self.checkpoint is None:
            return self
        if self.checkpoint.tenant_id != self.tenant_id:
            raise ValueError("checkpoint.tenant_id must match tenant_id")
        return self

    @property
    def channel_id(self) -> str:
        return self.tenant_id


class ChannelTalkFullSyncFetchResult(BaseModel):
    """fetch 단계가 남기는 typed 결과.

    UserChat list sweep policy는 execution request가 아니라 fetch 단계에서 고정한다.
    """

    model_config = ConfigDict(extra="forbid")

    states: tuple[ChannelTalkUserChatState, ...]
    sync_window: FullSyncWindow
    bundles: tuple[ChannelTalkFetchedUserChat, ...] = ()
    managers_by_id: dict[str, ChannelTalkManagerMetadata] = Field(default_factory=dict)
    fetched_record_ids: tuple[str, ...] = ()
    next_checkpoint: ChannelTalkFullSyncCheckpoint | None = None

    @field_validator("states")
    @classmethod
    def _validate_states(
        cls,
        value: tuple[ChannelTalkUserChatState, ...],
    ) -> tuple[ChannelTalkUserChatState, ...]:
        if not value:
            raise ValueError("states must include at least one state")
        return value

    @field_validator("fetched_record_ids")
    @classmethod
    def _validate_record_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(require_text(item, "fetched_record_ids") for item in value)

    @model_validator(mode="after")
    def _validate_checkpoint_alignment(self) -> "ChannelTalkFullSyncFetchResult":
        if self.next_checkpoint is None:
            return self
        if self.next_checkpoint.state not in self.states:
            raise ValueError("next_checkpoint.state must be included in states")
        if self.next_checkpoint.window != self.sync_window:
            raise ValueError("next_checkpoint.window must match sync_window")
        return self


class ChannelTalkFullSyncTransformResult(BaseModel):
    """transform 단계가 남기는 typed 결과."""

    model_config = ConfigDict(extra="forbid")

    documents: tuple["ChannelTalkPreparedDocument", ...] = ()


class ChannelTalkFullSyncSummaryResult(BaseModel):
    """summarize 단계 결과. 현재는 no-op여도 pipeline slot을 유지한다."""

    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False
    document_count: int = 0
    included_message_count: int = 0
    excluded_message_count: int = 0


class ChannelTalkFullSyncPersistResult(BaseModel):
    """persist 단계 결과. 최종 materialization/storage 경계를 나타낸다."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()


class ChannelTalkPreparedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    page_content: str
    logical_metadata: ChannelTalkUserChatLogicalMetadata
    storage_metadata: dict[str, object]

    @field_validator("document_id", "page_content")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)

    @property
    def contextual_content(self) -> str:
        return self.logical_metadata.base.contextual_content


class ChannelTalkFullSyncExecutionResult(FullSyncExecutionResult):
    """Channel Talk full sync 실행의 최종 typed 결과."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["user_chat"] = "user_chat"
    collected_count: int = 0
    document_count: int = 0
    fetched: ChannelTalkFullSyncFetchResult
    transformed: ChannelTalkFullSyncTransformResult
    summary: ChannelTalkFullSyncSummaryResult
    persisted: ChannelTalkFullSyncPersistResult

    @property
    def channel_id(self) -> str:
        return self.tenant_id


class ChannelTalkFullSyncAdapter:
    """
    Channel Talk full sync
    """

    def __init__(
        self,
        *,
        fetcher: ChannelTalkFullSyncFetcher | None = None,
        connection_loader=load_channel_talk_connection,
        repository_factory=None,
        enable_summarization: bool = True,
        summarizer: SummarizerService | None = None,
    ) -> None:
        self.fetcher = fetcher or ChannelTalkFullSyncFetcher()
        self._connection_loader = connection_loader
        self._repository_factory = repository_factory or self._build_repository
        if not enable_summarization:
            self.summarizer = None
        elif summarizer is not None:
            self.summarizer = summarizer
        else:
            self.summarizer = get_summarizer_service()
        self._repository: PGVectorRepository | None = None

    async def fetch(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
    ) -> ChannelTalkFullSyncFetchResult:
        fetch_states = self._default_fetch_states()
        self._validate_checkpoint_window(
            execution=execution,
            sync_window=sync_window,
            fetch_states=fetch_states,
        )
        connection = await self._load_connection(execution=execution)
        managers_by_id = await self.fetcher.fetch_managers_by_id(
            connection=connection,
        )
        fetched_user_chats = await self.fetcher.fetch_user_chats(
            connection=connection,
            states=fetch_states,
            sync_window=sync_window,
            checkpoint_state=(
                execution.checkpoint.state if execution.checkpoint is not None else None
            ),
            checkpoint_cursor=(
                execution.checkpoint.next_cursor
                if execution.checkpoint is not None
                else None
            ),
        )
        return ChannelTalkFullSyncFetchResult(
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
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        fetched: ChannelTalkFullSyncFetchResult,
    ) -> ChannelTalkFullSyncTransformResult:
        return ChannelTalkFullSyncTransformResult(
            documents=tuple(
                self._build_prepared_document(
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
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        transformed: ChannelTalkFullSyncTransformResult,
    ) -> ChannelTalkFullSyncSummaryResult:
        _ = sync_window
        included_message_count = sum(
            document.logical_metadata.user_chat_core.messages.included_message_count
            for document in transformed.documents
        )
        excluded_message_count = sum(
            document.logical_metadata.user_chat_core.messages.excluded_message_count
            for document in transformed.documents
        )
        if self.summarizer is None or not transformed.documents:
            return ChannelTalkFullSyncSummaryResult(
                summary_applied=False,
                document_count=len(transformed.documents),
                included_message_count=included_message_count,
                excluded_message_count=excluded_message_count,
            )

        requests = [
            SummarizeRequest(
                content=document.contextual_content,
                source_type="channel_talk_user_chat",
            )
            for document in transformed.documents
        ]
        summarized = await self.summarizer.summarize_batch(
            requests,
            audit_context=execution.audit_context,
            context=(
                "entity_type=user_chat,"
                f"channel_id={execution.channel_id},"
                f"doc_count={len(transformed.documents)}"
            ),
        )
        for document, summary in zip(transformed.documents, summarized):
            document.page_content = summary

        return ChannelTalkFullSyncSummaryResult(
            summary_applied=bool(transformed.documents),
            document_count=len(transformed.documents),
            included_message_count=included_message_count,
            excluded_message_count=excluded_message_count,
        )

    async def persist(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        transformed: ChannelTalkFullSyncTransformResult,
        summary: ChannelTalkFullSyncSummaryResult,
    ) -> ChannelTalkFullSyncPersistResult:
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
        return ChannelTalkFullSyncPersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
        )

    def build_result(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        fetched: ChannelTalkFullSyncFetchResult,
        transformed: ChannelTalkFullSyncTransformResult,
        summary: ChannelTalkFullSyncSummaryResult,
        persisted: ChannelTalkFullSyncPersistResult,
    ) -> ChannelTalkFullSyncExecutionResult:
        _ = sync_window
        return ChannelTalkFullSyncExecutionResult(
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
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
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
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        fetched_user_chats: ChannelTalkFetchedUserChatsResult,
    ) -> ChannelTalkFullSyncCheckpoint | None:
        if fetched_user_chats.next_checkpoint_state is None:
            return None
        return ChannelTalkFullSyncCheckpoint(
            tenant_id=execution.tenant_id,
            state=fetched_user_chats.next_checkpoint_state,
            window=sync_window,
            next_cursor=fetched_user_chats.next_checkpoint_cursor,
        )

    async def _load_connection(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
    ) -> ChannelTalkCredentialsRecord:
        connection = await run_in_threadpool(self._connection_loader)
        if connection is None:
            raise ValueError("channel_talk is not connected")
        if connection.channel_id != execution.channel_id:
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel"
            )
        require_text(connection.access_key, "access_key")
        require_text(connection.access_secret, "access_secret")
        return connection

    async def _get_repository(self) -> PGVectorRepository:
        if self._repository is None:
            repository = self._repository_factory()
            try:
                repository.ensure_initialized()
            except RuntimeError:
                await repository.initialize(None)
            self._repository = repository
        return self._repository

    @staticmethod
    def _build_repository() -> PGVectorRepository:
        return get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )

    def _build_prepared_document(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        bundle: ChannelTalkFetchedUserChat,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> ChannelTalkPreparedDocument:
        included_messages, excluded_count = self._partition_messages(bundle.messages)
        last_message_at = max(
            (
                message.created_at or message.updated_at
                for message in bundle.messages
                if message.created_at is not None or message.updated_at is not None
            ),
            default=None,
        )
        author_types = tuple(
            dict.fromkeys(
                filter(
                    None,
                    [
                        (
                            message.author.author_type
                            if message.author is not None
                            else message.person_type
                        )
                        or message.person_type
                        for message in bundle.messages
                    ],
                )
            )
        )
        contains_bot_messages = any(
            message.author is not None and message.author.is_bot
            for message in bundle.messages
        )
        contains_private_events = any(
            message.is_private is True for message in bundle.messages
        )
        contains_form_messages = any(
            message.form is not None for message in bundle.messages
        )

        contextual_content = self._build_contextual_content(
            detail=bundle.detail,
            included_messages=included_messages,
            managers_by_id=managers_by_id,
        )
        customer = bundle.detail.customer
        assignee_id = bundle.detail.assignment.assignee_id
        assignee_manager = (
            managers_by_id.get(assignee_id)
            if assignee_id is not None
            else None
        )
        assignee_name = (
            bundle.detail.assignment.assignee_name
            or (assignee_manager.name if assignee_manager is not None else None)
        )
        assignee_email = (
            bundle.detail.assignment.assignee_email
            or (assignee_manager.email if assignee_manager is not None else None)
        )
        manager_names = self._resolve_manager_names(
            manager_ids=bundle.detail.assignment.manager_ids,
            managers_by_id=managers_by_id,
            fallback_managers=bundle.detail.assignment.managers,
        )
        manager_role_ids = self._resolve_manager_role_ids(
            manager_ids=bundle.detail.assignment.manager_ids,
            managers_by_id=managers_by_id,
            fallback_managers=bundle.detail.assignment.managers,
        )
        logical_metadata = ChannelTalkUserChatLogicalMetadata(
            base=DocumentBaseMetadata(
                source="channel_talk",
                record_id=bundle.detail.user_chat_id,
                url=self._build_desk_url(
                    channel_id=execution.channel_id,
                    user_chat_id=bundle.detail.user_chat_id,
                ),
                created_at=bundle.detail.timing.created_at,
                updated_at=(
                    bundle.detail.timing.desk_updated_at
                    or bundle.detail.timing.updated_at
                    or last_message_at
                ),
                synced_at=sync_window.window_end,
                contextual_content=contextual_content,
            ),
            user_chat_core=ChannelTalkUserChatCoreMetadata(
                chat=ChannelTalkUserChatChatMetadata(
                    channel_id=execution.channel_id,
                    user_chat_id=bundle.detail.user_chat_id,
                    state=bundle.detail.state.value,
                    managed=bundle.detail.managed,
                    priority=bundle.detail.priority,
                    name=bundle.detail.name,
                    description=bundle.detail.description,
                    goal_state=bundle.detail.goal_state,
                ),
                customer=ChannelTalkUserChatCustomerMetadata(
                    user_id=(
                        customer.external_user_id
                        if customer is not None
                        else bundle.list_item.user_id
                    ),
                    member_id=(
                        customer.member_id
                        if customer is not None
                        else bundle.list_item.member_id
                    ),
                    veil_id=customer.veil_id if customer is not None else None,
                    unified_id=customer.unified_id if customer is not None else None,
                    type=customer.user_type if customer is not None else None,
                    name=customer.name if customer is not None else None,
                    email=customer.email if customer is not None else None,
                    mobile_number=(
                        customer.mobile_number if customer is not None else None
                    ),
                    avatar_url=customer.avatar_url if customer is not None else None,
                    language=customer.language if customer is not None else None,
                    country=customer.country if customer is not None else None,
                    city=customer.city if customer is not None else None,
                    time_zone=None,
                ),
                assignment=ChannelTalkUserChatAssignmentMetadata(
                    manager_ids=list(bundle.detail.assignment.manager_ids),
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    assignee_email=assignee_email,
                    first_assignee_id_after_open=(
                        bundle.detail.assignment.first_assignee_id_after_open
                    ),
                    manager_names=manager_names,
                    manager_role_ids=manager_role_ids,
                ),
                messages=ChannelTalkUserChatMessageMetadata(
                    message_ids=[message.message_id for message in bundle.messages],
                    last_message_at=last_message_at,
                    included_message_count=len(included_messages),
                    excluded_message_count=excluded_count,
                    author_types=list(author_types),
                    contains_bot_messages=contains_bot_messages,
                    contains_private_events=contains_private_events,
                    contains_form_messages=contains_form_messages,
                ),
                timing=ChannelTalkUserChatTimingMetadata(
                    first_opened_at=bundle.detail.timing.first_opened_at,
                    opened_at=bundle.detail.timing.opened_at,
                    first_asked_at=bundle.detail.timing.first_asked_at,
                    first_replied_at=bundle.detail.timing.first_replied_at,
                    first_replied_at_after_open=(
                        bundle.detail.timing.first_replied_at_after_open
                    ),
                    front_updated_at=bundle.detail.timing.front_updated_at,
                    desk_updated_at=bundle.detail.timing.desk_updated_at,
                    follow_up_triggered_at=(
                        bundle.detail.timing.follow_up_triggered_at
                    ),
                    closed_at=bundle.detail.timing.closed_at,
                    snoozed_at=bundle.detail.timing.snoozed_at,
                ),
                metrics=ChannelTalkUserChatMetricsMetadata(
                    waiting_time=bundle.detail.metrics.waiting_time,
                    avg_reply_time=bundle.detail.metrics.avg_reply_time,
                    total_reply_time=bundle.detail.metrics.total_reply_time,
                    reply_count=bundle.detail.metrics.reply_count,
                    operation_waiting_time=bundle.detail.metrics.operation_waiting_time,
                    operation_avg_reply_time=(
                        bundle.detail.metrics.operation_avg_reply_time
                    ),
                    operation_total_reply_time=(
                        bundle.detail.metrics.operation_total_reply_time
                    ),
                    operation_reply_count=(
                        bundle.detail.metrics.operation_reply_count
                    ),
                ),
                anchors=ChannelTalkUserChatAnchorsMetadata(
                    front_message_id=bundle.detail.anchors.front_message_id,
                    desk_message_id=bundle.detail.anchors.desk_message_id,
                    user_last_message_id=bundle.detail.anchors.user_last_message_id,
                ),
                tags=ChannelTalkUserChatTagsMetadata(
                    keys=[tag.key for tag in bundle.detail.tags if tag.key is not None],
                    names=[tag.name for tag in bundle.detail.tags if tag.name is not None],
                ),
                chunk=ChannelTalkUserChatChunkMetadata(
                    chunk_index=0,
                    chunk_count=1,
                ),
            ),
        )
        return ChannelTalkPreparedDocument(
            document_id=self._build_document_id(
                channel_id=execution.channel_id,
                user_chat_id=bundle.detail.user_chat_id,
            ),
            page_content=contextual_content,
            logical_metadata=logical_metadata,
            storage_metadata=logical_metadata.to_storage_metadata(),
        )

    @staticmethod
    def _build_document_id(
        *,
        channel_id: str,
        user_chat_id: str,
    ) -> str:
        return f"channel_talk:user_chat:{channel_id}:{user_chat_id}"

    @staticmethod
    def _build_desk_url(
        *,
        channel_id: str,
        user_chat_id: str,
    ) -> str:
        return f"https://desk.channel.io/#/channels/{channel_id}/user_chats/{user_chat_id}"

    def _partition_messages(
        self,
        messages: tuple[ChannelTalkUserChatMessage, ...],
    ) -> tuple[tuple[ChannelTalkUserChatMessage, ...], int]:
        included: list[ChannelTalkUserChatMessage] = []
        excluded_count = 0
        for message in messages:
            if self._should_include_message(message):
                included.append(message)
                continue
            excluded_count += 1
        return tuple(included), excluded_count

    @staticmethod
    def _should_include_message(message: ChannelTalkUserChatMessage) -> bool:
        return bool(
            str(message.plain_text or "").strip()
            or message.form is not None
            or message.log is not None
            or message.attachments
            or message.buttons
            or message.web_page is not None
        )

    def _build_contextual_content(
        self,
        *,
        detail,
        included_messages: tuple[ChannelTalkUserChatMessage, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str:
        customer = detail.customer
        title = detail.description or detail.name
        lines: list[str] = []
        if title:
            lines.append(str(title).strip())
        if customer is not None:
            customer_parts = [
                customer.name,
                customer.email,
                customer.mobile_number,
            ]
            customer_label = " / ".join(
                dict.fromkeys(
                    item.strip() for item in customer_parts if item and item.strip()
                )
            )
            if customer_label:
                lines.append(f"User: {customer_label}")
        assignee_name = self._resolve_assignee_name(
            detail=detail,
            managers_by_id=managers_by_id,
        )
        if assignee_name:
            lines.append(f"Assignee: {assignee_name}")
        manager_names = self._resolve_manager_names(
            manager_ids=detail.assignment.manager_ids,
            managers_by_id=managers_by_id,
            fallback_managers=detail.assignment.managers,
        )
        if manager_names:
            lines.append(f"Managers: {', '.join(manager_names)}")
        if detail.tags:
            tags = ", ".join(
                tag.name or tag.key or ""
                for tag in detail.tags
                if (tag.name or tag.key)
            )
            if tags:
                lines.append(f"Tags: {tags}")
        lines.append("")
        lines.append("Conversation:")
        if included_messages:
            lines.extend(
                self._format_message_line(
                    message,
                    customer=customer,
                    managers_by_id=managers_by_id,
                )
                for message in included_messages
            )
        else:
            lines.append("(포함된 메시지 없음)")
        return "\n".join(lines)

    @classmethod
    def _format_message_line(
        cls,
        message: ChannelTalkUserChatMessage,
        *,
        customer: ChannelTalkUserFoundation | None,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str:
        if message.log is not None:
            return f"[시스템] System: {cls._render_log_message(message.log)}"
        author_label = cls._resolve_message_author_label(
            message=message,
            customer=customer,
            managers_by_id=managers_by_id,
        )
        content = cls._render_message_content(message)
        prefix = cls._message_prefix(message)
        if prefix:
            return f"{prefix} {author_label}: {content}"
        return f"{author_label}: {content}"

    @classmethod
    def _resolve_message_author_label(
        cls,
        *,
        message: ChannelTalkUserChatMessage,
        customer: ChannelTalkUserFoundation | None,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str:
        author = message.author
        if author is None:
            return message.person_type or "Unknown"
        if author.user_id is not None:
            return "Customer"
        if author.manager_id is not None:
            return cls._manager_display_name(
                manager_id=author.manager_id,
                managers_by_id=managers_by_id,
            ) or author.name or "Manager"
        return author.name or author.bot_name or author.author_type or "Unknown"

    @classmethod
    def _message_prefix(cls, message: ChannelTalkUserChatMessage) -> str | None:
        if message.log is not None:
            return "[시스템]"
        if message.form is not None:
            return "[입력폼]"
        if message.attachments:
            return "[파일]"
        if message.buttons:
            return "[버튼]"
        if message.is_private is True:
            return "[내부대화]"
        return None

    @classmethod
    def _render_message_content(cls, message: ChannelTalkUserChatMessage) -> str:
        if message.log is not None:
            return cls._render_log_message(message.log)
        content_parts: list[str] = []
        plain_text = str(message.plain_text or "").strip()
        form_text = (
            cls._render_form_message(message.form)
            if message.form is not None
            else ""
        )
        if message.form is not None:
            if plain_text and form_text:
                content_parts.append(plain_text)
                if not cls._content_contains_form_text(
                    content=plain_text,
                    form_text=form_text,
                ):
                    content_parts.append(form_text)
            else:
                content_parts.append(plain_text or form_text)
        elif plain_text:
            content_parts.append(plain_text)
        if message.attachments:
            content_parts.append(cls._render_attachments(message.attachments))
        if message.buttons:
            content_parts.append(cls._render_buttons(message.buttons))
        if message.web_page is not None:
            web_page_text = cls._render_web_page(message.web_page)
            if web_page_text and not cls._content_contains_web_page(
                content_parts=content_parts,
                web_page=message.web_page,
            ):
                content_parts.append(web_page_text)
        return " | ".join(item for item in content_parts if item) or "(내용 없음)"

    @staticmethod
    def _content_contains_form_text(
        *,
        content: str,
        form_text: str,
    ) -> bool:
        form_parts = [
            part.strip()
            for part in form_text.replace(" / ", "\n").splitlines()
            if part.strip()
        ]
        return bool(form_parts) and all(part in content for part in form_parts)

    @staticmethod
    def _render_form_message(message_form: ChannelTalkUserChatMessageForm) -> str:
        parts = [
            f"{item.label}: {item.value}"
            if item.label and item.value
            else item.value or item.label
            for item in message_form.inputs
        ]
        return " / ".join(item for item in parts if item) or (
            message_form.form_type or ""
        )

    @staticmethod
    def _render_attachments(
        attachments: list[ChannelTalkUserChatMessageAttachment],
    ) -> str:
        return " / ".join(
            " ".join(
                item
                for item in [
                    attachment.name or attachment.file_key,
                    f"({attachment.content_type})" if attachment.content_type else None,
                ]
                if item
            )
            for attachment in attachments
        )

    @staticmethod
    def _render_buttons(
        buttons: list[ChannelTalkUserChatMessageButton],
    ) -> str:
        return "버튼: " + " / ".join(
            " ".join(
                item
                for item in [
                    button.text or button.value or button.action,
                    f"({button.url})" if button.url else None,
                ]
                if item
            )
            for button in buttons
        )

    @staticmethod
    def _render_web_page(web_page: ChannelTalkUserChatMessageWebPage) -> str:
        return " | ".join(
            item
            for item in [
                web_page.title,
                web_page.url,
                web_page.description,
            ]
            if item
        )

    @staticmethod
    def _content_contains_web_page(
        *,
        content_parts: list[str],
        web_page: ChannelTalkUserChatMessageWebPage,
    ) -> bool:
        content = "\n".join(content_parts)
        expected_parts = [
            web_page.title,
            web_page.url,
            web_page.description,
        ]
        return all(part in content for part in expected_parts if part)

    @staticmethod
    def _render_log_message(message_log: ChannelTalkUserChatMessageLog) -> str:
        return message_log.action or message_log.log_type or "system event"

    @classmethod
    def _resolve_assignee_name(
        cls,
        *,
        detail,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str | None:
        if detail.assignment.assignee_name:
            return detail.assignment.assignee_name
        assignee_id = detail.assignment.assignee_id
        if assignee_id is None:
            return None
        return cls._manager_display_name(
            manager_id=assignee_id,
            managers_by_id=managers_by_id,
        )

    @classmethod
    def _resolve_manager_names(
        cls,
        *,
        manager_ids: tuple[str, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
        fallback_managers,
    ) -> list[str]:
        fallback_names = {
            manager.manager_id: manager.name
            for manager in fallback_managers
            if manager.name is not None
        }
        names: list[str] = []
        for manager_id in manager_ids:
            name = cls._manager_display_name(
                manager_id=manager_id,
                managers_by_id=managers_by_id,
            ) or fallback_names.get(manager_id)
            if name:
                names.append(name)
        return list(dict.fromkeys(names))

    @staticmethod
    def _resolve_manager_role_ids(
        *,
        manager_ids: tuple[str, ...],
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
        fallback_managers,
    ) -> list[str]:
        fallback_role_ids = {
            manager.manager_id: manager.role_id
            for manager in fallback_managers
            if manager.role_id is not None
        }
        role_ids: list[str] = []
        for manager_id in manager_ids:
            manager = managers_by_id.get(manager_id)
            role_id = (manager.role_id if manager is not None else None) or (
                fallback_role_ids.get(manager_id)
            )
            if role_id:
                role_ids.append(role_id)
        return list(dict.fromkeys(role_ids))

    @staticmethod
    def _manager_display_name(
        *,
        manager_id: str,
        managers_by_id: dict[str, ChannelTalkManagerMetadata],
    ) -> str | None:
        manager = managers_by_id.get(manager_id)
        if manager is None:
            return None
        return manager.name or manager.email


ChannelTalkPreparedDocument.model_rebuild()
ChannelTalkFullSyncTransformResult.model_rebuild()
