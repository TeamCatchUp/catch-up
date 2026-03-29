from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncDispatchStatus
from catchup.sync.dispatch.types import DispatchContext


def build_snapshot_url(base_url: str | None, job_id: str) -> str | None:
    if not base_url:
        return None

    base = base_url.rstrip("/")
    return f"{base}/api/v1/sync/jobs/{job_id}"


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
    base_url: str | None,
    message: str = "active full sync already exists for this scope",
) -> SyncDispatchResult:
    snapshot_url = None
    if job_id is not None:
        snapshot_url = build_snapshot_url(base_url, job_id)

    return SyncDispatchResult(
        status=SyncDispatchStatus.CONFLICT,
        connector=connector,
        scope_id=scope_id,
        job_id=job_id,
        message=message,
        snapshot_url=snapshot_url,
    )


def build_accepted_response(
    *,
    context: DispatchContext,
    db_event_ids: list[str],
    queued_targets: int,
    base_url: str | None,
) -> SyncDispatchResult:
    snapshot_url = build_snapshot_url(base_url, context.job_id)

    return SyncDispatchResult(
        status=SyncDispatchStatus.ACCEPTED,
        connector=context.connector,
        scope_id=context.scope_id,
        job_id=context.job_id,
        event_ids=list(db_event_ids),
        total_targets=len(db_event_ids),
        queued_targets=queued_targets,
        message="sync dispatch accepted",
        snapshot_url=snapshot_url,
    )
