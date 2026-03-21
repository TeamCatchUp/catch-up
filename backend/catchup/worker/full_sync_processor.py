from __future__ import annotations

import logging

from fastapi.concurrency import run_in_threadpool

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus, SyncJobStatus, SyncType
from catchup.db.sync import (
    SyncEventPublishResultInput,
    claim_events_for_republish,
    claim_event_for_processing,
    count_events_by_job,
    complete_job_failed,
    complete_job_success,
    get_event,
    get_job,
    mark_event_failed,
    mark_event_retrying,
    mark_event_success,
    record_event_publish_outcomes,
    requeue_retrying_event,
    start_job,
    summarize_events_by_job,
)
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import (
    ClaimState,
    FullSyncContext,
    SyncStreamMessage,
    SyncStreamTask,
)
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.sync.stream_runtime.stream_queue import publish_task
from catchup.sync.event_publisher.stream_task_builder import (
    build_stream_task_from_persisted_event,
)
from catchup.worker.common import (
    build_job_status_event,
    build_target_status_event,
    deadletter,
    publish_status_event,
    select_handler,
)
from catchup.worker.schemas import ClaimResult, FailureResult, JobFinalizeResult

logger = logging.getLogger(__name__)


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
) -> FailureResult:
    with SessionLocal() as db:
        try:
            marked = mark_event_failed(db, context.event_id)
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


# Republish 이전에 Event 상태를 RETRYING / PENDING으로 변경
def _prepare_republish_sync(context: FullSyncContext) -> None:
    with SessionLocal() as db:
        try:
            event = get_event(db, context.event_id)
            if event is None:
                raise RuntimeError(f"event not found for republish: {context.event_id}")

            if not mark_event_retrying(db, context.event_id):
                raise RuntimeError("failed to transition IN_PROGRESS -> RETRYING")

            if not requeue_retrying_event(db, context.event_id):
                raise RuntimeError("failed to transition RETRYING -> PENDING")

            db.commit()
        except Exception:
            db.rollback()
            raise


# Republish 직전에 Publish 상태를 확인하고, Stream Task 조립
def _claim_republish_task_sync(context: FullSyncContext) -> SyncStreamTask:
    with SessionLocal() as db:
        try:
            if not claim_events_for_republish(db, event_ids=[context.event_id]):
                raise RuntimeError("failed to transition publish state to PUBLISHING")

            event = get_event(db, context.event_id)
            if event is None:
                raise RuntimeError(f"event not found for republish: {context.event_id}")

            task = build_stream_task_from_persisted_event(
                event=event,
                fallback_scope_id=context.scope_id,
            )

            db.commit()
            return task
        except Exception:
            db.rollback()
            raise


# Republish 결과를 published/failed 으로 기록
def _record_republish_outcome_sync(
    context: FullSyncContext,
    *,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if message_id is None and error_message is None:
        raise ValueError("republish outcome requires message_id or error_message")

    published: list[SyncEventPublishResultInput] = []
    failed_event_ids: list[str] = []

    if message_id is not None:
        published = [
            SyncEventPublishResultInput(
                event_id=context.event_id,
                stream_message_id=message_id,
            )
        ]
    else:
        failed_event_ids = [context.event_id]

    with SessionLocal() as db:
        try:
            if not record_event_publish_outcomes(
                db,
                published=published,
                failed_event_ids=failed_event_ids,
                publish_error=error_message,
            ):
                db.rollback()
                raise RuntimeError("failed to persist republish outcome state")

            db.commit()
        except Exception:
            db.rollback()
            raise


# Full Sync 실패 Event를 다시 Stream으로 Publishing
async def _republish_full_sync_event(
    *,
    context: FullSyncContext,
) -> None:
    await run_in_threadpool(_prepare_republish_sync, context)
    task = await run_in_threadpool(_claim_republish_task_sync, context)

    try:
        message_id = await publish_task(task)
    except Exception as exc:
        await run_in_threadpool(
            _record_republish_outcome_sync,
            context,
            error_message=str(exc),
        )
        raise

    await run_in_threadpool(
        _record_republish_outcome_sync,
        context,
        message_id=message_id,
    )


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
    should_retry = next_attempt < context.max_attempts

    if should_retry:
        try:
            await _republish_full_sync_event(context=context)
        except Exception:
            logger.exception(
                "[%s][FULL][WORKER] Event republish failed: event_id=%s, next_attempt=%s",
                context.connector.upper(),
                context.event_id,
                next_attempt,
            )
            return
        else:
            await publish_status_event(
                build_target_status_event(
                    context=context,
                    event_type=SyncStatusEventType.TARGET_REQUEUED,
                    status=SyncEventStatus.RETRYING.value,
                    attempt=next_attempt,
                )
            )
            await handler.on_target_requeued(
                context=context,
                next_attempt=next_attempt,
                error_summary=error_summary,
            )
            logger.warning(
                "[%s][FULL][WORKER] Target requeued: event_id=%s, next_attempt=%s, error=%s",
                context.connector.upper(),
                context.event_id,
                next_attempt,
                error_summary,
            )
            return

    failure = await run_in_threadpool(
        _mark_event_failed_sync,
        context,
        should_retry=should_retry,
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

    await publish_status_event(
        build_target_status_event(
            context=context,
            event_type=SyncStatusEventType.TARGET_FAILED,
            status=SyncEventStatus.FAILED.value,
            attempt=next_attempt,
        )
    )
    await handler.on_target_failed(
        context=context,
        next_attempt=next_attempt,
        error_summary=error_summary,
        retryable=failure.should_retry,
    )
    logger.error(
        "[%s][FULL][WORKER] Target failed: event_id=%s, attempt=%s, retryable=%s, error=%s",
        context.connector.upper(),
        context.event_id,
        next_attempt,
        failure.should_retry,
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
        await publish_status_event(
            build_job_status_event(
                context=context,
                event_type=SyncStatusEventType.JOB_COMPLETED,
                status=SyncJobStatus.SUCCESS.value,
                total_targets=result.total_targets,
                completed_targets=result.completed_targets,
                failed_targets=result.failed_targets,
                requeued_targets=result.requeued_targets,
            )
        )
        await handler.on_job_completed(
            context=context,
            total_targets=result.total_targets,
            completed_targets=result.completed_targets,
            failed_targets=result.failed_targets,
            requeued_targets=result.requeued_targets,
        )
        return

    await publish_status_event(
        build_job_status_event(
            context=context,
            event_type=SyncStatusEventType.JOB_FAILED,
            status=SyncJobStatus.FAILED.value,
            total_targets=result.total_targets,
            completed_targets=result.completed_targets,
            failed_targets=result.failed_targets,
            requeued_targets=result.requeued_targets,
        )
    )
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
            await publish_status_event(
                build_job_status_event(
                    context=context,
                    event_type=SyncStatusEventType.JOB_STARTED,
                    status=SyncJobStatus.IN_PROGRESS.value,
                    total_targets=claim.total_targets,
                )
            )
            await handler.on_job_started(
                context=context,
                total_targets=claim.total_targets,
            )

        await publish_status_event(
            build_target_status_event(
                context=context,
                event_type=SyncStatusEventType.TARGET_STARTED,
                status=SyncEventStatus.IN_PROGRESS.value,
            )
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

        await publish_status_event(
            build_target_status_event(
                context=context,
                event_type=SyncStatusEventType.TARGET_COMPLETED,
                status=SyncEventStatus.SUCCESS.value,
            )
        )
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
