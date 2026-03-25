from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType
from catchup.sync.common.schemas import SyncTargetType


@dataclass(slots=True, frozen=True)
class SyncJobTargetSnapshotResult:
    target_id: str
    target_name: str
    status: SyncEventStatus
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SyncJobSnapshotResult:
    job_id: str
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    status: SyncJobStatus
    created_at: str
    started_at: str | None
    completed_at: str | None
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    targets: list[SyncJobTargetSnapshotResult] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(slots=True, frozen=True)
class SyncTargetResult:
    target_id: str
    display_name: str
    target_type: SyncTargetType
    is_accessible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SyncTargetsResult:
    connector: SyncConnector
    scope_id: str
    total_targets: int
    targets: list[SyncTargetResult] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SyncScopeStatusResult:
    job_id: str
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    status: SyncJobStatus
    requested_at: str
    started_at: str | None
    completed_at: str | None
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(slots=True, frozen=True)
class SyncJobSummaryResult:
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None
