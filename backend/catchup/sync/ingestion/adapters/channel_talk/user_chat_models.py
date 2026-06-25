from __future__ import annotations

from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connectors.channel_talk.core.user_chat_fetch_models import (
    ChannelTalkFetchedUserChat,
)
from catchup.connectors.channel_talk.core.user_chat_fetch_models import (
    ChannelTalkFetchedUserChatsResult as ChannelTalkFetchedUserChatsResult,
)
from catchup.connectors.channel_talk.core.user_chat_fetch_models import (
    ChannelTalkUserChatFullSyncConnection as ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.document_format import ChannelTalkUserChatLogicalMetadata
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.utils.validation import require_text


class ChannelTalkUserChatPreparedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    page_content: str
    logical_metadata: ChannelTalkUserChatLogicalMetadata
    storage_metadata: dict[str, object]

    @field_validator("document_id", "page_content")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @property
    def contextual_content(self) -> str:
        return self.logical_metadata.base.contextual_content


class ChannelTalkUserChatFullSyncCheckpoint(BaseModel):
    """Adapter-local resume shape for the UserChat full-sync lane."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    target: Literal["user_chat"] = CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
    state: ChannelTalkUserChatState
    window: SyncWindow
    next_cursor: str | None = None

    @field_validator("tenant_id")
    @classmethod
    def _validate_tenant_id(cls, value: str) -> str:
        return require_text(value, "tenant_id")


class ChannelTalkUserChatSyncExecutionRequest(SyncExecutionRequest):
    """Target-oriented execution request for the UserChat ingestion lane."""

    connector: Literal[SyncConnector.CHANNEL_TALK] = SyncConnector.CHANNEL_TALK
    target: Literal["user_chat"] = CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
    checkpoint: ChannelTalkUserChatFullSyncCheckpoint | None = None
    audit_context: SyncAuditContext | None = None

    @model_validator(mode="after")
    def _validate_checkpoint_alignment(
        self,
    ) -> "ChannelTalkUserChatSyncExecutionRequest":
        if self.checkpoint is None:
            return self
        if self.checkpoint.tenant_id != self.tenant_id:
            raise ValueError("checkpoint.tenant_id must match tenant_id")
        return self

    @property
    def channel_id(self) -> str:
        return self.tenant_id


class ChannelTalkUserChatIncrementalExecutionRequest(
    ChannelTalkUserChatSyncExecutionRequest
):
    """Exact-refresh execution request for one UserChat record."""

    user_chat_id: str

    @field_validator("user_chat_id")
    @classmethod
    def _validate_user_chat_id(cls, value: str) -> str:
        return require_text(value, "user_chat_id")


class ChannelTalkUserChatFullSyncFetchResult(BaseModel):
    """Typed fetch result for the UserChat lane."""

    model_config = ConfigDict(extra="forbid")

    states: tuple[ChannelTalkUserChatState, ...]
    sync_window: SyncWindow
    bundles: tuple[ChannelTalkFetchedUserChat, ...] = ()
    managers_by_id: dict[str, ChannelTalkManagerMetadata] = Field(default_factory=dict)
    fetched_record_ids: tuple[str, ...] = ()
    failed_record_ids: tuple[str, ...] = ()
    next_checkpoint: ChannelTalkUserChatFullSyncCheckpoint | None = None

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
    def _validate_checkpoint_alignment(self) -> "ChannelTalkUserChatFullSyncFetchResult":
        if self.next_checkpoint is None:
            return self
        if self.next_checkpoint.state not in self.states:
            raise ValueError("next_checkpoint.state must be included in states")
        if self.next_checkpoint.window != self.sync_window:
            raise ValueError("next_checkpoint.window must match sync_window")
        return self


class ChannelTalkUserChatFullSyncTransformResult(BaseModel):
    """Typed transform result for materialized UserChat documents."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    documents: tuple[ChannelTalkUserChatPreparedDocument, ...] = ()
    v2_documents: tuple[Document, ...] = ()
    v2_failed_ids: tuple[str, ...] = ()


class ChannelTalkUserChatFullSyncSummaryResult(BaseModel):
    """Typed summary result for the UserChat lane."""

    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False
    document_count: int = 0
    included_message_count: int = 0
    excluded_message_count: int = 0
    v2_documents: tuple[Document, ...] = ()


class ChannelTalkUserChatFullSyncPersistResult(BaseModel):
    """Typed persist result for the UserChat lane."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()
    v2_error_count: int = 0
    v2_failed_ids: tuple[str, ...] = ()


class ChannelTalkUserChatSyncExecutionResult(SyncExecutionResult):
    """Final typed result for a UserChat ingestion run."""

    connector: Literal[SyncConnector.CHANNEL_TALK] = SyncConnector.CHANNEL_TALK
    target: Literal["user_chat", "user_chat_v2_backfill"] = (
        CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
    )
    collected_count: int = 0
    document_count: int = 0
    persisted_count: int = 0
    failed_count: int = 0
    v2_failed_count: int = 0
    v2_failed_ids: tuple[str, ...] = ()
    fetched: ChannelTalkUserChatFullSyncFetchResult
    transformed: ChannelTalkUserChatFullSyncTransformResult
    summary: ChannelTalkUserChatFullSyncSummaryResult
    persisted: ChannelTalkUserChatFullSyncPersistResult

    @property
    def channel_id(self) -> str:
        return self.tenant_id


class ChannelTalkUserChatIncrementalExecutionResult(
    ChannelTalkUserChatSyncExecutionResult
):
    """Final typed result for one UserChat exact-refresh run."""


class ChannelTalkUserChatV2BackfillSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]

    @field_validator("langchain_id", "record_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("embedding")
    @classmethod
    def _validate_embedding(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("embedding must not be empty")
        return value


class ChannelTalkUserChatV2BackfillExecutionRequest(
    ChannelTalkUserChatSyncExecutionRequest
):
    target: Literal["user_chat_v2_backfill"] = "user_chat_v2_backfill"
    seeds: tuple[ChannelTalkUserChatV2BackfillSeed, ...]

    def log_context(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "record_type": "user_chat",
            "seed_count": len(self.seeds),
        }


ChannelTalkUserChatFullSyncExecutionRequest = ChannelTalkUserChatSyncExecutionRequest
ChannelTalkUserChatFullSyncExecutionResult = ChannelTalkUserChatSyncExecutionResult
