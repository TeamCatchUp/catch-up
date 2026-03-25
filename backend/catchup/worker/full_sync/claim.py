from __future__ import annotations

from catchup.configs.constants import FULL_SYNC_EVENT_SCHEMA_VERSION
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.sync import claim_event_for_processing
from catchup.db.sync import count_events_by_job
from catchup.db.sync import get_event
from catchup.db.sync import get_job
from catchup.db.sync import requeue_retrying_event
from catchup.db.sync import set_event_execution_phase
from catchup.db.sync import start_job
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncStreamTask
from catchup.worker.schemas import ClaimResult


def _build_full_sync_context(
    *,
    task: SyncStreamTask,
    claimed,
    job,
) -> FullSyncContext:
    metadata = (
        dict(claimed.resource_metadata)
        if isinstance(claimed.resource_metadata, dict)
        else {}
    )
    scope_id = str(metadata.get("scope_id") or job.scope_id)
    target_id = str(claimed.resource_id)

    if claimed.stage is not None and "stage" not in metadata:
        metadata["stage"] = claimed.stage
    if claimed.range_start is not None and "range_start" not in metadata:
        metadata["range_start"] = claimed.range_start.isoformat()
    if claimed.range_end is not None and "range_end" not in metadata:
        metadata["range_end"] = claimed.range_end.isoformat()
    if claimed.chunk_index is not None and "chunk_index" not in metadata:
        metadata["chunk_index"] = claimed.chunk_index
    if claimed.chunk_total is not None and "chunk_total" not in metadata:
        metadata["chunk_total"] = claimed.chunk_total
    if claimed.range_watermark is not None and "range_watermark" not in metadata:
        metadata["range_watermark"] = claimed.range_watermark.isoformat()

    sync_from_ts = task.sync_from_ts
    if sync_from_ts is None:
        raw_sync_from_ts = metadata.get("sync_from_ts")
        if raw_sync_from_ts is not None:
            normalized_sync_from_ts = str(raw_sync_from_ts).strip()
            sync_from_ts = normalized_sync_from_ts or None

    return FullSyncContext(
        event_id=claimed.event_id,
        job_id=claimed.job_id,
        connector=claimed.connector,
        scope_id=scope_id,
        target_type=claimed.resource_type,
        target_id=target_id,
        target_name=str(metadata.get("target_name") or target_id),
        sync_from_ts=sync_from_ts,
        attempt=int(claimed.attempt),
        max_attempts=int(claimed.max_attempts),
        metadata=metadata,
    )


def _claim_event(task: SyncStreamTask) -> ClaimResult:
    with SessionLocal() as db:
        try:
            event = get_event(db, task.event_id)
            if event is None:
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_NOT_FOUND)

            if event.job_id != task.job_id:
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_JOB_MISMATCH)

            event_metadata = (
                event.resource_metadata
                if isinstance(event.resource_metadata, dict)
                else {}
            )
            event_schema_version = event_metadata.get("event_schema_version")
            if event_schema_version not in (
                FULL_SYNC_EVENT_SCHEMA_VERSION,
                str(FULL_SYNC_EVENT_SCHEMA_VERSION),
            ):
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_ALREADY_TERMINAL)

            if event.status in {
                SyncEventStatus.SUCCESS,
                SyncEventStatus.FAILED,
            }:
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_ALREADY_TERMINAL)

            if event.status == SyncEventStatus.RETRYING:
                if not requeue_retrying_event(db, task.event_id):
                    db.rollback()
                    return ClaimResult(state=ClaimState.EVENT_CAS_CONFLICT)

            if not claim_event_for_processing(db, task.event_id):
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_CAS_CONFLICT)

            claimed = get_event(db, task.event_id)
            if claimed is None:
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_NOT_FOUND)

            job = get_job(db, task.job_id)
            if job is None:
                db.rollback()
                return ClaimResult(state=ClaimState.JOB_NOT_FOUND)

            context = _build_full_sync_context(
                task=task,
                claimed=claimed,
                job=job,
            )

            if not set_event_execution_phase(
                db,
                event_id=task.event_id,
                execution_phase="collecting_ids",
                from_statuses=[SyncEventStatus.IN_PROGRESS],
            ):
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_CAS_CONFLICT)

            job_started = start_job(db, task.job_id)
            total_targets = 0
            if job_started:
                total_targets = count_events_by_job(db, job_id=task.job_id)

            db.commit()
            return ClaimResult(
                state=ClaimState.CLAIMED,
                context=context,
                job_started=job_started,
                total_targets=total_targets,
            )
        except Exception:
            db.rollback()
            raise
