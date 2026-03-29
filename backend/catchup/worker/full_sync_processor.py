from __future__ import annotations

import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType
from catchup.db.sync import claim_event_for_processing
from catchup.db.sync import complete_job_failed
from catchup.db.sync import complete_job_success
from catchup.db.sync import count_events_by_job
from catchup.db.sync import get_event
from catchup.db.sync import get_job
from catchup.db.sync import mark_event_failed
from catchup.db.sync import mark_event_retrying
from catchup.db.sync import mark_event_success
from catchup.db.sync import requeue_retrying_event
from catchup.db.sync import start_job
from catchup.db.sync import summarize_events_by_job
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.retry_policy import is_retryable_sync_error
from catchup.sync.common.retry_policy import resolve_retry_delay
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.worker.common import deadletter
from catchup.worker.common import select_handler
from catchup.worker.schemas import ClaimResult
from catchup.worker.schemas import FailureResult
from catchup.worker.schemas import JobFinalizeResult

logger = logging.getLogger(__name__)


def _full_sync_retry_delay(exc: Exception, attempt: int) -> timedelta:
    return resolve_retry_delay(
        exc=exc,
        attempt=attempt,
        base_delay_seconds=settings.SYNC_JOB_RETRY_BASE_DELAY_SECONDS,
        max_delay_seconds=settings.SYNC_JOB_RETRY_MAX_DELAY_SECONDS,
    )


# PersistedSyncEvent + JobID = FullSyncContext
def _build_full_sync_context(
    *,
    task: SyncStreamTask,
    claimed,
    job,
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


# Full Sync Status DB 상태조회 -> ClaimResult
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

# Full Sync 성공시 상태 전이 트랜잭션 관리
def _mark_event_success_sync(context: FullSyncContext) -> bool:
    with SessionLocal() as db:
        try:
            updated = mark_event_success(db, event_id=context.event_id)
            if not updated:
                db.rollback()
                return False

            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


# Full Sync 실패시 상태 전이 트랜잭션 관리
def _mark_event_failed_sync(
    context: FullSyncContext,
    *,
    should_retry: bool,
    error_summary: str,
) -> FailureResult:
    with SessionLocal() as db:
        try:
            marked = mark_event_failed(
                db,
                context.event_id,
                last_error=error_summary,
            )
            if not marked:
                db.rollback()
                return FailureResult(
                    marked=False,
                    should_retry=should_retry,
                )

            db.commit()
            return FailureResult(
                marked=True,
                should_retry=should_retry,
            )
        except Exception:
            db.rollback()
            raise


# Full Sync retry를 RETRYING 상태로 예약
def _schedule_event_retry_sync(
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


# Full Sync 예외를 retry / termainal failed 으로 분기
async def _handle_event_failure(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    exc: Exception,
    handler: IngestionHandlerProtocol,
) -> None:
    error_summary = str(exc)
    next_attempt = context.attempt + 1
    retryable = is_retryable_sync_error(exc)
    should_retry = retryable and next_attempt < context.max_attempts

    if should_retry:
        retry_delay = _full_sync_retry_delay(exc, next_attempt)
        next_retry_at = datetime.now(timezone.utc) + retry_delay
        scheduled = await run_in_threadpool(
            _schedule_event_retry_sync,
            context,
            next_retry_at=next_retry_at,
            error_summary=error_summary,
        )
        if not scheduled:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="failed to transition event to RETRYING",
            )
            logger.error(
                "[%s][FULL][WORKER] Retry schedule transition skipped: event_id=%s, next_attempt=%s",
                context.connector.upper(),
                context.event_id,
                next_attempt,
            )
            return

        await handler.on_target_requeued(
            context=context,
            next_attempt=next_attempt,
            error_summary=error_summary,
        )
        logger.warning(
            "[%s][FULL][WORKER] Target scheduled for retry: event_id=%s, next_attempt=%s, retry_at=%s, error=%s",
            context.connector.upper(),
            context.event_id,
            next_attempt,
            next_retry_at.isoformat(),
            error_summary,
        )
        return

    failure = await run_in_threadpool(
        _mark_event_failed_sync,
        context,
        should_retry=should_retry,
        error_summary=error_summary,
    )
    if not failure.marked:
        await deadletter(
            message=message,
            reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
            error_message="failed to transition event to FAILED",
        )
        logger.error(
            "[%s][FULL][WORKER] Event failure transition skipped: event_id=%s",
            context.connector.upper(),
            context.event_id,
        )
        return

    await handler.on_target_failed(
        context=context,
        next_attempt=next_attempt,
        error_summary=error_summary,
        retryable=retryable,
    )
    logger.error(
        "[%s][FULL][WORKER] Target failed: event_id=%s, attempt=%s, retryable=%s, error=%s",
        context.connector.upper(),
        context.event_id,
        next_attempt,
        retryable,
        error_summary,
    )


# 특정 Job ID에 대해서 모든 Event가 완료되었는지 검증
def _finalize_job_if_done_sync(context: FullSyncContext) -> JobFinalizeResult:
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


# full sync job 종료 확정 후 상태 이벤트와 handler hook 을 실행한다.
async def _finalize_job_if_done(
    context: FullSyncContext,
    handler: IngestionHandlerProtocol,
) -> None:
    result = await run_in_threadpool(_finalize_job_if_done_sync, context)
    if not result.finalized or result.status is None:
        return

    if result.status == SyncJobStatus.SUCCESS:
        await handler.on_job_completed(
            context=context,
            total_targets=result.total_targets,
            completed_targets=result.completed_targets,
            failed_targets=result.failed_targets,
            requeued_targets=result.requeued_targets,
        )
        return

    await handler.on_job_failed(
        context=context,
        total_targets=result.total_targets,
        failed_targets=result.failed_targets,
    )


# Full Sync Job Orchestration
async def process_full_sync_message(
    message: SyncStreamMessage,
    service_cache: dict[str, object],
) -> None:
    task = message.task
    context: FullSyncContext | None = None
    handler: IngestionHandlerProtocol | None = None

    try:
        claim = await run_in_threadpool(_claim_event, task)

        if claim.state == ClaimState.EVENT_NOT_FOUND:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_NOT_FOUND,
                error_message="sync event not found",
            )
            return

        if claim.state == ClaimState.JOB_NOT_FOUND:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_NOT_FOUND,
                error_message="sync job not found",
            )
            return

        if claim.state == ClaimState.EVENT_JOB_MISMATCH:
            logger.error(
                "[SYNC][WORKER] Event/Job mismatch: event_id=%s, stream_job_id=%s",
                task.event_id,
                task.job_id,
            )
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="event_id and job_id mismatch",
            )
            return

        if claim.state == ClaimState.EVENT_ALREADY_TERMINAL:
            logger.warning(
                "[SYNC][WORKER] Duplicate event skipped: job_id=%s, event_id=%s",
                task.job_id,
                task.event_id,
            )
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_ALREADY_TERMINAL,
                error_message="event already terminal",
            )
            return

        if claim.state == ClaimState.EVENT_CAS_CONFLICT:
            logger.warning(
                "[SYNC][WORKER] Event CAS conflict: job_id=%s, event_id=%s",
                task.job_id,
                task.event_id,
            )
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="event status transition CAS conflict",
            )
            return

        context = claim.context
        if context is None:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected empty claim context",
            )
            return
        if not isinstance(context, FullSyncContext):
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected full sync claim context type",
            )
            return

        handler = select_handler(context)
        if handler is None:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"unsupported handler: connector={context.connector}, "
                    f"sync_type={context.sync_type}"
                ),
            )
            return

        if claim.job_started:
            await handler.on_job_started(
                context=context,
                total_targets=claim.total_targets,
            )

        await handler.on_target_started(context=context)

        result = await handler.handle(
            context=context,
            service_cache=service_cache,
        )
        if not await run_in_threadpool(_mark_event_success_sync, context):
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="failed to transition event to SUCCESS",
            )
            return

        await handler.on_target_completed(context=context, result=result)
    except Exception as exc:
        if context is None:
            logger.exception(
                "[SYNC][WORKER] Message processing failed before claim: job_id=%s, event_id=%s",
                task.job_id,
                task.event_id,
            )
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message=str(exc),
            )
            return

        if handler is None:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"unsupported handler: connector={context.connector}, "
                    f"sync_type={context.sync_type}"
                ),
            )
            return

        await _handle_event_failure(
            context=context,
            message=message,
            exc=exc,
            handler=handler,
        )
    finally:
        try:
            if context is not None and handler is not None:
                await _finalize_job_if_done(context, handler)
        finally:
            pass
