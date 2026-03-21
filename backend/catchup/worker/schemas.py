from __future__ import annotations

from dataclasses import dataclass

from catchup.db.models import SyncJobStatus
from catchup.sync.common.schemas import ClaimState, SyncContext


@dataclass(slots=True)
class ClaimResult:
    state: ClaimState
    context: SyncContext | None = None
    job_started: bool = False
    total_targets: int = 0


@dataclass(slots=True)
class FailureResult:
    marked: bool
    should_retry: bool


@dataclass(slots=True)
class JobFinalizeResult:
    finalized: bool = False
    status: SyncJobStatus | None = None
    total_targets: int = 0
    completed_targets: int = 0
    failed_targets: int = 0
    requeued_targets: int = 0
