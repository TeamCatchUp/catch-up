from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connector_core.document_format import ChannelTalkUserChatLogicalMetadata
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.full_sync import FullSyncExecutionRequest
from catchup.connector_core.ports.full_sync import FullSyncExecutionResult
from catchup.connector_core.ports.full_sync import FullSyncWindow


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


class ChannelTalkUserChatState(StrEnum):
    OPENED = "opened"
    CLOSED = "closed"
    SNOOZED = "snoozed"


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
        return _require_text(value, "tenant_id")


class ChannelTalkFullSyncExecutionRequest(FullSyncExecutionRequest):
    """Target-oriented execution request for the current Channel Talk full-sync lane."""

    connector: Literal[ConnectorKey.CHANNEL_TALK] = ConnectorKey.CHANNEL_TALK
    target: Literal["user_chat"] = "user_chat"
    checkpoint: ChannelTalkFullSyncCheckpoint | None = None

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
        return tuple(_require_text(item, "fetched_record_ids") for item in value)

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

    documents: tuple[ChannelTalkUserChatLogicalMetadata, ...] = ()


class ChannelTalkFullSyncSummaryResult(BaseModel):
    """summarize 단계 결과. 현재는 no-op여도 pipeline slot을 유지한다."""

    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False


class ChannelTalkFullSyncPersistResult(BaseModel):
    """persist 단계 결과. 최종 materialization/storage 경계를 나타낸다."""

    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0


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
        return ChannelTalkFullSyncFetchResult(
            states=fetch_states,
            sync_window=sync_window,
            next_checkpoint=execution.checkpoint,
        )

    async def transform(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        fetched: ChannelTalkFullSyncFetchResult,
    ) -> ChannelTalkFullSyncTransformResult:
        _ = execution
        _ = sync_window
        _ = fetched
        return ChannelTalkFullSyncTransformResult()

    async def summarize(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        transformed: ChannelTalkFullSyncTransformResult,
    ) -> ChannelTalkFullSyncSummaryResult:
        """선택적 summarize slot. 현재 계약에서는 no-op를 허용한다."""
        _ = execution
        _ = sync_window
        _ = transformed
        return ChannelTalkFullSyncSummaryResult()

    async def persist(
        self,
        *,
        execution: ChannelTalkFullSyncExecutionRequest,
        sync_window: FullSyncWindow,
        transformed: ChannelTalkFullSyncTransformResult,
        summary: ChannelTalkFullSyncSummaryResult,
    ) -> ChannelTalkFullSyncPersistResult:
        """최종 materialization/storage slot. Raw fetch 로직은 여전히 다른 계층에 둔다."""
        _ = execution
        _ = sync_window
        _ = transformed
        _ = summary
        return ChannelTalkFullSyncPersistResult()

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
