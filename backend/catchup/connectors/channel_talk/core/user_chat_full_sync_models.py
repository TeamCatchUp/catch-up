from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connector_core.document_format import ChannelTalkUserChatLogicalMetadata
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.sync_ingestion import SyncExecutionRequest
from catchup.connector_core.ports.sync_ingestion import SyncExecutionResult
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.sync.audit import SyncAuditContext
from catchup.utils.validation import require_text


class ChannelTalkUserChatFullSyncConnection(BaseModel):
    """Validated Channel Talk credentials for the UserChat fetch boundary."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    channel_name: str
    access_key: str
    access_secret: str

    @field_validator("channel_id", "channel_name", "access_key", "access_secret")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @classmethod
    def from_credentials_record(
        cls,
        record: ChannelTalkCredentialsRecord,
    ) -> "ChannelTalkUserChatFullSyncConnection":
        return cls(
            channel_id=record.channel_id,
            channel_name=record.channel_name,
            access_key=require_text(record.access_key, "access_key"),
            access_secret=require_text(record.access_secret, "access_secret"),
        )


class ChannelTalkFetchedUserChat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ChannelTalkUserChatState
    channel_name: str
    list_item: ChannelTalkUserChatListItem
    detail: ChannelTalkUserChatDetail
    messages: tuple[ChannelTalkUserChatMessage, ...] = ()

    @field_validator("messages")
    @classmethod
    def _validate_messages(
        cls,
        value: tuple[ChannelTalkUserChatMessage, ...],
    ) -> tuple[ChannelTalkUserChatMessage, ...]:
        return tuple(value)


class ChannelTalkFetchedUserChatsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundles: tuple[ChannelTalkFetchedUserChat, ...] = ()
    next_checkpoint_state: ChannelTalkUserChatState | None = None
    next_checkpoint_cursor: str | None = None

    @model_validator(mode="after")
    def _validate_checkpoint_shape(self) -> "ChannelTalkFetchedUserChatsResult":
        if (
            self.next_checkpoint_cursor is not None
            and self.next_checkpoint_state is None
        ):
            raise ValueError(
                "next_checkpoint_state is required with next_checkpoint_cursor"
            )
        return self


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

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
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

    model_config = ConfigDict(extra="forbid")

    documents: tuple[ChannelTalkUserChatPreparedDocument, ...] = ()


class ChannelTalkUserChatFullSyncSummaryResult(BaseModel):
    """Typed summary result for the UserChat lane."""

    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False
    document_count: int = 0
    included_message_count: int = 0
    excluded_message_count: int = 0


class ChannelTalkUserChatFullSyncPersistResult(BaseModel):
    """Typed persist result for the UserChat lane."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()


class ChannelTalkUserChatSyncExecutionResult(SyncExecutionResult):
    """Final typed result for a UserChat ingestion run."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["user_chat"] = CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
    collected_count: int = 0
    document_count: int = 0
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


ChannelTalkUserChatFullSyncExecutionRequest = ChannelTalkUserChatSyncExecutionRequest
ChannelTalkUserChatFullSyncExecutionResult = ChannelTalkUserChatSyncExecutionResult
