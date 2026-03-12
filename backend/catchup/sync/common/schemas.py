from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_validator

from catchup.db.models import SyncConnector, SyncType


def _validate_epoch_ts(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    try:
        parsed = float(stripped)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be a UTC epoch seconds string"
        ) from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return stripped


class SyncDispatchStatus(StrEnum):
    ACCEPTED = "accepted"
    NO_EVENTS = "no_events"
    CONFLICT = "conflict"
    FAILED = "failed"


class SyncTrigger(StrEnum):
    API = "api"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


class SyncTargetType(StrEnum):
    RESOURCE = "resource"
    CHANNEL = "channel"
    REPOSITORY = "repository"
    PROJECT = "project"
    SPACE = "space"


class SyncEventKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class ClaimState(StrEnum):
    CLAIMED = "claimed"
    EVENT_NOT_FOUND = "event_not_found"
    EVENT_JOB_MISMATCH = "event_job_mismatch"
    EVENT_ALREADY_TERMINAL = "event_already_terminal"
    EVENT_CAS_CONFLICT = "event_cas_conflict"
    JOB_NOT_FOUND = "job_not_found"
    INVALID_INCREMENTAL_TASK = "invalid_incremental_task"
    RECORD_NOT_FOUND = "record_not_found"
    STALE_TASK = "stale_task"
    RECORD_CAS_CONFLICT = "record_cas_conflict"


@dataclass(slots=True, frozen=True)
class HandlerKey:
    connector: SyncConnector
    sync_type: SyncType

    @classmethod
    def of(
        cls,
        *,
        connector: SyncConnector | str,
        sync_type: SyncType | str,
    ) -> "HandlerKey":
        return cls(
            connector=SyncConnector(connector),
            sync_type=SyncType(sync_type),
        )


@dataclass(slots=True, frozen=True)
class FullSyncDispatchRequest:
    scope_id: str
    target_ids: list[str] | None = None
    sync_from_ts: str | None = None
    trigger: SyncTrigger = SyncTrigger.API

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger", SyncTrigger(self.trigger))
        object.__setattr__(
            self,
            "sync_from_ts",
            _validate_epoch_ts(self.sync_from_ts, field_name="sync_from_ts"),
        )


@dataclass(slots=True, frozen=True)
class SyncDispatchResult:
    """Dispatch 결과

    queued_targets : dispatch 시점에 queue publish 까지 성공한 target 수
    처리 진행 상황은 이후 job snapshot/status 에서 다시 조회
    """

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

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", SyncDispatchStatus(self.status))
        object.__setattr__(self, "connector", SyncConnector(self.connector))


@dataclass(slots=True, frozen=True)
class FullSyncTarget:
    target_type: SyncTargetType
    target_id: str
    target_name: str
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_type", SyncTargetType(self.target_type))


@dataclass(slots=True, frozen=True)
class FullSyncResolvedTargets:
    targets: list[FullSyncTarget] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SyncEventSeed:
    event_id: str
    target_type: SyncTargetType
    target_id: str
    target_name: str
    sync_from_ts: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    max_attempts: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_type", SyncTargetType(self.target_type))
        object.__setattr__(
            self,
            "sync_from_ts",
            _validate_epoch_ts(self.sync_from_ts, field_name="sync_from_ts"),
        )


@dataclass(slots=True, frozen=True)
class TargetSyncResult:
    synced_count: int = 0
    error_count: int = 0
    skipped: bool = False


class FullSyncTaskPayload(BaseModel):
    target_type: SyncTargetType = Field(default=SyncTargetType.RESOURCE)
    target_id: str = Field(..., description="target identifier")
    sync_from_ts: str | None = Field(
        default=None,
        description="absolute full sync start timestamp in UTC epoch seconds string",
    )

    @field_validator("target_id")
    @classmethod
    def _validate_target_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("target_id is empty")
        if stripped != value:
            raise ValueError("target_id must not include leading/trailing spaces")
        return value

    @field_validator("sync_from_ts")
    @classmethod
    def _validate_sync_from_ts(cls, value: str | None) -> str | None:
        return _validate_epoch_ts(value, field_name="sync_from_ts")

    def to_stream_fields(self) -> dict[str, str]:
        fields = {
            "target_type": self.target_type.value,
            "target_id": self.target_id,
        }
        if self.sync_from_ts is not None:
            fields["sync_from_ts"] = self.sync_from_ts
        return fields


class IncrementalSyncTaskPayload(FullSyncTaskPayload):
    record_key: str = Field(..., description="incremental record key")
    generation: int = Field(..., ge=1, description="incremental generation")
    record_type: str | None = Field(default=None, description="incremental record type")
    record_id: str | None = Field(default=None, description="incremental record id")
    parent_type: SyncTargetType = Field(..., description="incremental parent type")
    parent_id: str = Field(..., description="incremental parent id")
    event_kind: SyncEventKind = Field(..., description="incremental normalized event kind")
    last_event_at: str = Field(..., description="incremental last event timestamp")

    @field_validator("record_key", "parent_id", "last_event_at")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("required incremental field is empty")
        if stripped != value:
            raise ValueError("required incremental field must not include surrounding spaces")
        return value

    @field_validator("record_type", "record_id")
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("optional incremental field must not be blank")
        if stripped != value:
            raise ValueError("optional incremental field must not include surrounding spaces")
        return value

    def to_stream_fields(self) -> dict[str, str]:
        fields = super().to_stream_fields()
        fields.update(
            {
                "record_key": self.record_key,
                "generation": str(self.generation),
                "parent_type": self.parent_type.value,
                "parent_id": self.parent_id,
                "event_kind": self.event_kind.value,
                "last_event_at": self.last_event_at,
            }
        )
        if self.record_type is not None:
            fields["record_type"] = self.record_type
        if self.record_id is not None:
            fields["record_id"] = self.record_id
        return fields


SyncTaskPayload: TypeAlias = IncrementalSyncTaskPayload | FullSyncTaskPayload


class SyncStreamTask(BaseModel):
    event_id: str = Field(..., description="Global Unique Event ID")
    job_id: str = Field(..., description="Sync Job ID")
    connector: SyncConnector = Field(..., description="Connector key")
    sync_type: SyncType = Field(..., description="full | incremental")
    scope_id: str = Field(..., description="team_id / cloud_id / installation_id")
    payload: SyncTaskPayload = Field(..., description="typed task payload")
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)

    @field_validator("event_id", "job_id", "scope_id")
    @classmethod
    def _validate_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value is empty")
        if stripped != value:
            raise ValueError("value must not include leading/trailing spaces")
        return value

    @model_validator(mode="after")
    def _validate_payload_type(self) -> "SyncStreamTask":
        if self.sync_type == SyncType.FULL and type(self.payload) is not FullSyncTaskPayload:
            raise ValueError("full sync task requires FullSyncTaskPayload")
        if self.sync_type == SyncType.INCREMENTAL and not isinstance(
            self.payload,
            IncrementalSyncTaskPayload,
        ):
            raise ValueError("incremental sync task requires IncrementalSyncTaskPayload")
        return self

    @classmethod
    def full(
        cls,
        *,
        event_id: str,
        job_id: str,
        connector: SyncConnector | str,
        scope_id: str,
        target_type: SyncTargetType | str,
        target_id: str,
        sync_from_ts: str | None,
        attempt: int = 0,
        max_attempts: int = 3,
    ) -> "SyncStreamTask":
        return cls(
            event_id=event_id,
            job_id=job_id,
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            payload=FullSyncTaskPayload(
                target_type=target_type,
                target_id=target_id,
                sync_from_ts=sync_from_ts,
            ),
            attempt=attempt,
            max_attempts=max_attempts,
        )

    @classmethod
    def incremental(
        cls,
        *,
        event_id: str,
        job_id: str,
        connector: SyncConnector | str,
        scope_id: str,
        target_type: SyncTargetType | str,
        target_id: str,
        record_key: str,
        generation: int,
        record_type: str | None,
        record_id: str | None,
        parent_type: SyncTargetType | str,
        parent_id: str,
        event_kind: SyncEventKind | str,
        last_event_at: str,
        attempt: int = 0,
        max_attempts: int = 3,
    ) -> "SyncStreamTask":
        return cls(
            event_id=event_id,
            job_id=job_id,
            connector=connector,
            sync_type=SyncType.INCREMENTAL,
            scope_id=scope_id,
            payload=IncrementalSyncTaskPayload(
                target_type=target_type,
                target_id=target_id,
                record_key=record_key,
                generation=generation,
                record_type=record_type,
                record_id=record_id,
                parent_type=parent_type,
                parent_id=parent_id,
                event_kind=event_kind,
                last_event_at=last_event_at,
            ),
            attempt=attempt,
            max_attempts=max_attempts,
        )

    @property
    def target_type(self) -> SyncTargetType:
        return self.payload.target_type

    @property
    def target_id(self) -> str:
        return self.payload.target_id

    @property
    def record_key(self) -> str | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.record_key
        return None

    @property
    def generation(self) -> int | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.generation
        return None

    @property
    def record_type(self) -> str | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.record_type
        return None

    @property
    def record_id(self) -> str | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.record_id
        return None

    @property
    def parent_type(self) -> SyncTargetType | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.parent_type
        return None

    @property
    def parent_id(self) -> str | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.parent_id
        return None

    @property
    def event_kind(self) -> SyncEventKind | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.event_kind
        return None

    @property
    def last_event_at(self) -> str | None:
        if isinstance(self.payload, IncrementalSyncTaskPayload):
            return self.payload.last_event_at
        return None

    @property
    def sync_from_ts(self) -> str | None:
        return self.payload.sync_from_ts

    def to_stream_fields(self) -> dict[str, str]:
        fields = {
            "event_id": self.event_id,
            "job_id": self.job_id,
            "connector": self.connector.value,
            "sync_type": self.sync_type.value,
            "scope_id": self.scope_id,
            "attempt": str(self.attempt),
            "max_attempts": str(self.max_attempts),
        }
        fields.update(self.payload.to_stream_fields())
        return fields

    @classmethod
    def from_stream_fields(cls, fields: Mapping[str, Any]) -> "SyncStreamTask":
        event_id = fields.get("event_id")
        job_id = fields.get("job_id")
        connector = fields.get("connector")
        sync_type = fields.get("sync_type")
        scope_id = fields.get("scope_id")

        if (
            event_id is None
            or job_id is None
            or connector is None
            or sync_type is None
            or scope_id is None
        ):
            raise ValueError(
                "stream fields must include event_id, job_id, connector, sync_type, scope_id"
            )

        resolved_sync_type = SyncType(str(sync_type))
        if resolved_sync_type == SyncType.FULL:
            payload: SyncTaskPayload = FullSyncTaskPayload(
                target_type=str(fields.get("target_type") or SyncTargetType.RESOURCE.value),
                target_id=str(fields.get("target_id") or ""),
                sync_from_ts=(
                    str(fields.get("sync_from_ts"))
                    if fields.get("sync_from_ts") is not None
                    else None
                ),
            )
        else:
            payload = IncrementalSyncTaskPayload(
                target_type=str(fields.get("target_type") or SyncTargetType.RESOURCE.value),
                target_id=str(fields.get("target_id") or ""),
                record_key=str(fields.get("record_key") or ""),
                generation=int(fields.get("generation") or 0),
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
                parent_type=str(fields.get("parent_type") or ""),
                parent_id=str(fields.get("parent_id") or ""),
                event_kind=str(fields.get("event_kind") or ""),
                last_event_at=str(fields.get("last_event_at") or ""),
            )

        return cls(
            event_id=str(event_id),
            job_id=str(job_id),
            connector=str(connector),
            sync_type=resolved_sync_type,
            scope_id=str(scope_id),
            payload=payload,
            attempt=int(fields.get("attempt") or 0),
            max_attempts=max(1, int(fields.get("max_attempts") or 3)),
        )


class SyncStreamMessage(BaseModel):
    message_id: str = Field(..., description="Redis Stream Message ID")
    task: SyncStreamTask = Field(..., description="Parsed Stream Task Payload")


class SyncClaimBatch(BaseModel):
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
class SyncContextBase:
    event_id: str
    job_id: str
    connector: SyncConnector
    scope_id: str
    target_type: SyncTargetType
    target_id: str
    target_name: str
    attempt: int
    max_attempts: int

    def __post_init__(self) -> None:
        self.connector = SyncConnector(self.connector)
        self.target_type = SyncTargetType(self.target_type)


@dataclass(slots=True)
class FullSyncContext(SyncContextBase):
    sync_from_ts: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    sync_type: SyncType = field(init=False, default=SyncType.FULL)


@dataclass(slots=True)
class IncrementalSyncContext(SyncContextBase):
    record_key: str
    generation: int
    record_type: str | None = None
    record_id: str | None = None
    parent_type: SyncTargetType = SyncTargetType.RESOURCE
    parent_id: str = ""
    event_kind: SyncEventKind = SyncEventKind.UPDATED
    last_event_at: str = ""
    batch_sync_from: str | None = None
    batch_generation_ceiling: int | None = None
    sync_type: SyncType = field(init=False, default=SyncType.INCREMENTAL)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.parent_type = SyncTargetType(self.parent_type)
        self.event_kind = SyncEventKind(self.event_kind)


SyncContext: TypeAlias = FullSyncContext | IncrementalSyncContext
