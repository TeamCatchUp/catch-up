from __future__ import annotations

from typing import Any
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator

from catchup.connectors.slack.schemas import SlackThreadReply
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.utils.validation import require_text

SlackIncrementalEventKind = Literal["created", "updated", "deleted"]


class SlackMessageFullSyncExecutionRequest(SyncExecutionRequest):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    connector: Literal[SyncConnector.SLACK] = SyncConnector.SLACK
    target: Literal["message"] = "message"
    channel_id: str
    channel_name: str
    skip_delete: bool = True
    batch_index: int = 0
    cursor: str | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("channel_id", "channel_name")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    def log_context(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "skip_delete": self.skip_delete,
            "batch_index": self.batch_index,
            "cursor_present": bool(self.cursor),
        }


class SlackMessageIncrementalSyncExecutionRequest(SyncExecutionRequest):
    connector: Literal[SyncConnector.SLACK] = SyncConnector.SLACK
    target: Literal["message"] = "message"
    channel_id: str
    record_id: str
    event_kind: SlackIncrementalEventKind = "updated"
    audit_context: SyncAuditContext | None = None

    @field_validator("channel_id", "record_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def is_delete_event(self) -> bool:
        return self.event_kind == "deleted"

    def log_context(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "record_id": self.record_id,
            "event_kind": self.event_kind,
        }


class SlackMessageFetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    requested_count: int = 1
    parent_messages: tuple[dict[str, Any], ...] = ()
    reply_map: dict[str, tuple[SlackThreadReply, ...]] = Field(default_factory=dict)
    delete_document_ids: tuple[str, ...] = ()
    channel_name: str | None = None
    fetch_error_count: int = 0
    batch_index: int = 0
    is_last: bool = True
    next_cursor: str | None = None

    @property
    def parent_message_count(self) -> int:
        return len(self.parent_messages)

    @property
    def next_cursor_present(self) -> bool:
        return bool(self.next_cursor)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "parent_message_count": self.parent_message_count,
            "delete_document_count": len(self.delete_document_ids),
            "fetch_error_count": self.fetch_error_count,
            "is_last": self.is_last,
            "next_cursor_present": self.next_cursor_present,
        }


class SlackMessageTransformResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    requested_count: int = 1
    documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()
    delete_document_ids: tuple[str, ...] = ()
    channel_name: str | None = None
    error_count: int = 0
    latest_synced_ts: str | None = None

    @property
    def document_count(self) -> int:
        return len(self.documents)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "document_count": self.document_count,
            "delete_document_count": len(self.delete_document_ids),
            "error_count": self.error_count,
            "latest_synced_ts_present": bool(self.latest_synced_ts),
        }


class SlackMessageSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    summary_applied: bool = False
    documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "summary_applied": self.summary_applied,
            "document_count": len(self.documents),
        }


class SlackMessagePersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    deleted_count: int = 0
    error_count: int = 0
    skipped: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "error_count": self.error_count,
            "skipped": self.skipped,
        }


class SlackMessageSyncExecutionResult(SyncExecutionResult):
    connector: Literal[SyncConnector.SLACK] = SyncConnector.SLACK
    target: Literal["message"] = "message"
    persisted_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    skipped: bool = False
    fetched: SlackMessageFetchResult
    transformed: SlackMessageTransformResult
    summary: SlackMessageSummaryResult
    persisted: SlackMessagePersistResult
    batch_index: int = 0
    is_last: bool = True
    next_cursor: str | None = None
    checkpoint: str | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "failed_count": self.failed_count,
            "skipped": self.skipped,
            "is_last": self.is_last,
            "next_cursor_present": bool(self.next_cursor),
            "checkpoint_present": bool(self.checkpoint),
        }
