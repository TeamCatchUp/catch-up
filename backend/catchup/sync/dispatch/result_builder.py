from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncDispatchStatus
from catchup.sync.dispatch.types import DispatchContext


def build_no_events_response(
    *,
    connector: SyncConnector,
    scope_id: str,
) -> SyncDispatchResult:
    return SyncDispatchResult(
        status=SyncDispatchStatus.NO_EVENTS,
        connector=connector,
        scope_id=scope_id,
        total_targets=0,
        queued_targets=0,
        message="no sync events were generated for this request",
    )


def build_conflict_response(
    *,
    connector: SyncConnector,
    scope_id: str,
    job_id: str | None,
    message: str = "active full sync already exists for this scope",
) -> SyncDispatchResult:
    return SyncDispatchResult(
        status=SyncDispatchStatus.CONFLICT,
        connector=connector,
        scope_id=scope_id,
        job_id=job_id,
        message=message,
    )


def build_accepted_response(
    *,
    context: DispatchContext,
    db_event_ids: list[str],
    queued_targets: int,
) -> SyncDispatchResult:
    return SyncDispatchResult(
        status=SyncDispatchStatus.ACCEPTED,
        connector=context.connector,
        scope_id=context.scope_id,
        job_id=context.job_id,
        event_ids=list(db_event_ids),
        total_targets=len(db_event_ids),
        queued_targets=queued_targets,
        message="sync dispatch accepted",
    )
