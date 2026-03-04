from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator

from catchup.db.models import SyncConnector

SyncDispatchStatus = Literal["accepted", "no_events", "conflict", "failed"]


@dataclass(slots=True, frozen=True)
class FullSyncDispatchCommand:
    """커넥터 공통 Full Sync 요청."""

    scope_id: str
    target_ids: list[str] | None = None
    sync_days: int | None = None
    trigger: str = "api"


@dataclass(slots=True, frozen=True)
class IncrementalSyncDispatchCommand:
    """커넥터 공통 Incremental Sync 요청."""

    scope_id: str
    target_ids: list[str] | None = None
    trigger: str = "api"


@dataclass(slots=True, frozen=True)
class SyncDispatchResult:
    """커넥터 공통 Sync 요청 처리 결과."""

    status: SyncDispatchStatus
    connector: SyncConnector
    scope_id: str
    job_id: str | None = None
    event_ids: list[str] = field(default_factory=list)
    total_targets: int = 0
    queued_targets: int = 0
    dropped_targets: int = 0
    dropped_events: int = 0
    message: str | None = None
    snapshot_url: str | None = None
    stream_url: str | None = None


class SyncStreamTask(BaseModel):
    """Redis Stream에 저장되는 이벤트 단위 작업."""

    event_id: str = Field(..., description="Global Unique Event ID")
    job_id: str = Field(..., description="Sync Job ID")
    connector: str = Field(..., description="Connector key")
    sync_type: str = Field(default="full", description="full | incremental")
    scope_id: str = Field(default="", description="team_id / cloud_id / installation_id")
    target_type: str = Field(default="resource", description="channel/repository/project/space")
    target_id: str = Field(default="", description="target identifier")
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)

    @field_validator("event_id", "job_id", "connector")
    @classmethod
    def _validate_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value is empty")
        return normalized

    def to_stream_fields(self) -> dict[str, str]:
        return {
            "event_id": self.event_id,
            "job_id": self.job_id,
            "connector": self.connector,
            "sync_type": self.sync_type,
            "scope_id": self.scope_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "attempt": str(self.attempt),
            "max_attempts": str(self.max_attempts),
        }

    @classmethod
    def from_stream_fields(cls, fields: Mapping[str, Any]) -> "SyncStreamTask":
        event_id = fields.get("event_id")
        job_id = fields.get("job_id")
        connector = fields.get("connector")

        if event_id is None or job_id is None or connector is None:
            raise ValueError("stream fields must include event_id, job_id, connector")

        return cls(
            event_id=str(event_id),
            job_id=str(job_id),
            connector=str(connector),
            sync_type=str(fields.get("sync_type") or "full"),
            scope_id=str(fields.get("scope_id") or ""),
            target_type=str(fields.get("target_type") or "resource"),
            target_id=str(fields.get("target_id") or ""),
            attempt=int(fields.get("attempt") or 0),
            max_attempts=max(1, int(fields.get("max_attempts") or 3)),
        )


class SyncStreamMessage(BaseModel):
    message_id: str = Field(..., description="Redis Stream Message ID")
    task: SyncStreamTask = Field(..., description="Parsed Stream Task Payload")


class SyncClaimBatch(BaseModel):
    """XAUTOCLAIM 결과."""

    next_start_id: str = Field(..., description="Next cursor of XAUTOCLAIM")
    messages: list[SyncStreamMessage] = Field(
        default_factory=list,
        description="Claimed stream messages",
    )


@dataclass(slots=True)
class SyncEventContext:
    event_id: str
    job_id: str
    connector: str
    sync_type: str
    scope_id: str
    target_type: str
    target_id: str
    target_name: str
    attempt: int
    max_attempts: int
    metadata: dict[str, Any] = field(default_factory=dict)
