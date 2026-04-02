from __future__ import annotations

from datetime import datetime
from typing import Any

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus, SyncJobStatus, SyncType
from catchup.db.sync.repository import claim_event_for_processing, complete_job_failed, complete_job_success, count_events_by_job, get_event, get_job, mark_event_failed as update_event_failed, mark_event_retrying, mark_event_success as update_event_success, requeue_retrying_event, start_job, summarize_events_by_job
from catchup.sync.common.schemas import ClaimState, FullSyncContext, SyncStreamTask
from catchup.worker.schemas import ClaimResult, FailureResult, JobFinalizeResult

def build_full_sync_context(
    *,
    task: SyncStreamTask,
    claimed: Any,
    job: Any,
) -> FullSyncContext:
    metadata = (
        claimed.resource_metadata
        if isinstance(claimed.resource_metadata, dict)
        else {}
    )
    scope_id = str(metadata.get("scope_id") or job.scope_id)
    target_id = str(claimed.resource_id)

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

def claim_event(task: SyncStreamTask) -> ClaimResult:
    with SessionLocal() as db:
        try:
            event = get_event(db, task.event_id)
            if event is None:
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_NOT_FOUND)
            
            if event.job_id != task.job_id:
                db.rollback()
                return ClaimResult(state=ClaimState.EVENT_JOB_MISMATCH)
            
            if event.status in {SyncEventStatus.SUCCESS, SyncEventStatus.FAILED}:
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
            
            context = build_full_sync_context(task=task, claimed=claimed, job=job)

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

def mark_event_success_sync(context: FullSyncContext) -> bool:
    with SessionLocal() as db:
        try:
            updated = update_event_success(db, event_id=context.event_id)
            if not updated:
                db.rollback()
                return False
            
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

def mark_event_failed_sync(
    context: FullSyncContext,
    *,
    should_retry: bool,
    error_summary: str,
) -> FailureResult:
    with SessionLocal() as db:
        try:
            marked = update_event_failed(
                db,
                context.event_id,
                last_error=error_summary,
            )
            if not marked:
                db.rollback()
                return FailureResult(marked=False, should_retry=should_retry)
            db.commit()
            return FailureResult(marked=True, should_retry=should_retry)
        except Exception:
            db.rollback()
            raise

def schedule_event_retry_sync(
    context: FullSyncContext,
    *,
    next_retry_at: datetime,
    error_summary: str,
) -> bool:
    with SessionLocal() as db:
        try:
            scheduled = mark_event_retrying(
                db,
                context.event_id,
                next_retry_at=next_retry_at,
                last_error=error_summary,
                increment_attempt=True,
            )
            if not scheduled:
                db.rollback()
                return False
            
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

def finalize_job_if_done_sync(context: FullSyncContext) -> JobFinalizeResult:
    if context.sync_type != SyncType.FULL:
        return JobFinalizeResult()

    with SessionLocal() as db:
        try:
            job = get_job(db, context.job_id)
            if job is None:
                return JobFinalizeResult()

            if job.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
                return JobFinalizeResult()

            summary = summarize_events_by_job(db, job_id=context.job_id)
            if summary.total_targets == 0:
                return JobFinalizeResult()

            if summary.queued_targets > 0 or summary.processing_targets > 0:
                return JobFinalizeResult()

            if summary.failed_targets == 0:
                if not complete_job_success(db, context.job_id):
                    db.rollback()
                    return JobFinalizeResult()

                db.commit()
                return JobFinalizeResult(
                    finalized=True,
                    status=SyncJobStatus.SUCCESS,
                    total_targets=summary.total_targets,
                    completed_targets=summary.completed_targets,
                    failed_targets=summary.failed_targets,
                    requeued_targets=summary.requeued_targets,
                )

            if not complete_job_failed(db, context.job_id):
                db.rollback()
                return JobFinalizeResult()

            db.commit()
            return JobFinalizeResult(
                finalized=True,
                status=SyncJobStatus.FAILED,
                total_targets=summary.total_targets,
                completed_targets=summary.completed_targets,
                failed_targets=summary.failed_targets,
                requeued_targets=summary.requeued_targets,
            )
        except Exception:
            db.rollback()
            raise
