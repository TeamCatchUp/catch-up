from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator

from catchup.db.models import SyncConnector

SyncDispatchStatus = Literal["accepted", "no_events", "conflict", "failed"]

class SyncTrigger(StrEnum):
    API = "api"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


def _normalize_trigger(value: SyncTrigger | str) -> SyncTrigger:
    if isinstance(value, SyncTrigger):
        return value
    return SyncTrigger(str(value).strip().lower())


@dataclass(slots=True, frozen=True)
class FullSyncDispatchRequest:
    """커넥터 공통 Full Sync 요청."""

    scope_id: str
    target_ids: list[str] | None = None
    sync_days: int | None = None
    trigger: SyncTrigger = SyncTrigger.API

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger", _normalize_trigger(self.trigger))


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
    message: str | None = None
    snapshot_url: str | None = None
    stream_url: str | None = None


@dataclass(slots=True, frozen=True)
class FullSyncTarget:
    target_type: str
    target_id: str
    target_name: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class FullSyncResolvedTargets:
    targets: list[FullSyncTarget] = field(default_factory=list)
    invalid_target_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SyncEventSeed:
    event_id: str
    target_type: str
    target_id: str
    target_name: str
    sync_from: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    max_attempts: int = 3


class SyncStreamTask(BaseModel):
    """Redis Stream에 저장되는 이벤트 단위 작업."""

    event_id: str = Field(..., description="Global Unique Event ID")
    job_id: str = Field(..., description="Sync Job ID")
    connector: str = Field(..., description="Connector key")
    sync_type: str = Field(default="full", description="full | incremental")
    scope_id: str = Field(default="", description="team_id / cloud_id / installation_id")
    target_type: str = Field(default="resource", description="channel/repository/project/space")
    target_id: str = Field(default="", description="target identifier")
    record_key: str | None = Field(default=None, description="incremental record key")
    generation: int | None = Field(default=None, ge=1, description="incremental generation")
    record_type: str | None = Field(default=None, description="incremental record type")
    record_id: str | None = Field(default=None, description="incremental record id")
    parent_type: str | None = Field(default=None, description="incremental parent type")
    parent_id: str | None = Field(default=None, description="incremental parent id")
    event_kind: str | None = Field(default=None, description="incremental normalized event kind")
    last_event_at: str | None = Field(default=None, description="incremental last event timestamp")
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)

    @field_validator("event_id", "job_id", "connector")
    @classmethod
    def _validate_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value is empty")
        return normalized

    @field_validator(
        "record_key",
        "record_type",
        "record_id",
        "parent_type",
        "parent_id",
        "event_kind",
        "last_event_at",
    )
    @classmethod
    def _validate_optional_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def to_stream_fields(self) -> dict[str, str]:
        fields = {
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
        if self.record_key is not None:
            fields["record_key"] = self.record_key
        if self.generation is not None:
            fields["generation"] = str(self.generation)
        if self.record_type is not None:
            fields["record_type"] = self.record_type
        if self.record_id is not None:
            fields["record_id"] = self.record_id
        if self.parent_type is not None:
            fields["parent_type"] = self.parent_type
        if self.parent_id is not None:
            fields["parent_id"] = self.parent_id
        if self.event_kind is not None:
            fields["event_kind"] = self.event_kind
        if self.last_event_at is not None:
            fields["last_event_at"] = self.last_event_at
        return fields

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
            record_key=(
                str(fields.get("record_key"))
                if fields.get("record_key") is not None
                else None
            ),
            generation=(
                int(fields.get("generation"))
                if fields.get("generation") is not None and str(fields.get("generation")).strip()
                else None
            ),
            record_type=(
                str(fields.get("record_type"))
                if fields.get("record_type") is not None
                else None
            ),
            record_id=(
                str(fields.get("record_id"))
                if fields.get("record_id") is not None
                else None
            ),
            parent_type=(
                str(fields.get("parent_type"))
                if fields.get("parent_type") is not None
                else None
            ),
            parent_id=(
                str(fields.get("parent_id"))
                if fields.get("parent_id") is not None
                else None
            ),
            event_kind=(
                str(fields.get("event_kind"))
                if fields.get("event_kind") is not None
                else None
            ),
            last_event_at=(
                str(fields.get("last_event_at"))
                if fields.get("last_event_at") is not None
                else None
            ),
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


class PublishTasksResult(BaseModel):
    requested_count: int = Field(default=0, ge=0)
    published_count: int = Field(default=0, ge=0)
    message_ids: list[str] = Field(default_factory=list)
    partial_success: bool = Field(default=False)
    error_message: str | None = None
    failed_at_index: int | None = Field(default=None, ge=0)
    failed_event_id: str | None = None


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
    sync_from: str | None
    attempt: int
    max_attempts: int
    record_key: str | None = None
    generation: int | None = None
    record_type: str | None = None
    record_id: str | None = None
    parent_type: str | None = None
    parent_id: str | None = None
    event_kind: str | None = None
    last_event_at: str | None = None
    batch_sync_from: str | None = None
    batch_generation_ceiling: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
