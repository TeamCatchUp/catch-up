from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.configs.constants import FULL_SYNC_EVENT_SCHEMA_VERSION
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType
from catchup.db.sync import claim_event_for_processing
from catchup.db.sync import clear_event_missing_records
from catchup.db.sync import complete_job_failed
from catchup.db.sync import complete_job_success
from catchup.db.sync import count_events_by_job
from catchup.db.sync import get_event
from catchup.db.sync import get_job
from catchup.db.sync import replace_event_missing_records
from catchup.db.sync import SyncEventMissingRecordInput
from catchup.db.sync import mark_event_failed
from catchup.db.sync import mark_event_retrying
from catchup.db.sync import mark_event_success
from catchup.db.sync import requeue_retrying_event
from catchup.db.sync import set_event_execution_phase
from catchup.db.sync import start_job
from catchup.db.sync import summarize_events_by_job
from catchup.db.sync import update_event_resource_metadata
from catchup.sync.common.protocols import FullSyncCollectingHandlerProtocol
from catchup.sync.common.protocols import FullSyncValidatingHandlerProtocol
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.canonical_ids import split_canonical_id
from catchup.sync.common.retry_policy import is_retryable_sync_error
from catchup.sync.common.retry_policy import resolve_retry_delay
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import FullSyncRepairStatus
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.common.schemas import FullSyncValidationResult
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.worker.common import build_job_status_event
from catchup.worker.common import build_target_status_event
from catchup.worker.common import deadletter
from catchup.worker.common import publish_status_event
from catchup.worker.common import select_handler
from catchup.worker.schemas import ClaimResult
from catchup.worker.schemas import FailureResult
from catchup.worker.schemas import JobFinalizeResult

logger = structlog.get_logger()


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

            event_metadata = (
                event.resource_metadata
                if isinstance(event.resource_metadata, dict)
                else {}
            )
            
            # 레거시 Event Claim 방지
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

def _update_event_metadata_sync(
    *,
    event_id: str,
    values: dict[str, object],
) -> bool:
    with SessionLocal() as db:
        try:
            updated = update_event_resource_metadata(
                db,
                event_id=event_id,
                values=values,
                from_statuses=[SyncEventStatus.IN_PROGRESS],
            )
            if not updated:
                db.rollback()
                return False

            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


def _store_event_missing_records_sync(
    *,
    event_id: str,
    missing_ids: list[str],
) -> int:
    items: list[SyncEventMissingRecordInput] = []
    for canonical_id in missing_ids:
        try:
            _, record_type, record_id = split_canonical_id(canonical_id)
        except ValueError:
            continue
        items.append(
            SyncEventMissingRecordInput(
                event_id=event_id,
                record_type=record_type,
                record_id=record_id,
            )
        )

    with SessionLocal() as db:
        try:
            stored_count = replace_event_missing_records(
                db,
                event_id=event_id,
                items=items,
            )
            db.commit()
            return stored_count
        except Exception:
            db.rollback()
            raise


def _clear_event_missing_records_sync(*, event_id: str) -> int:
    with SessionLocal() as db:
        try:
            cleared_count = clear_event_missing_records(db, event_id=event_id)
            db.commit()
            return cleared_count
        except Exception:
            db.rollback()
            raise


def _has_retry_attempt_remaining(context: FullSyncContext) -> bool:
    return (context.attempt + 1) < context.max_attempts


def _missing_ratio(validation_result: FullSyncValidationResult) -> float:
    if validation_result.expected_count <= 0:
        return 0.0
    return validation_result.missing_count / validation_result.expected_count

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
                "full_sync_retry_schedule_transition_skipped",
                connector=context.connector.value,
                event_id=context.event_id,
                next_attempt=next_attempt,
            )
            return

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
            "full_sync_target_retry_scheduled",
            connector=context.connector.value,
            event_id=context.event_id,
            next_attempt=next_attempt,
            retry_at=next_retry_at.isoformat(),
            error=error_summary,
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
            "full_sync_event_failure_transition_skipped",
            connector=context.connector.value,
            event_id=context.event_id,
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
        retryable=retryable,
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


async def _complete_event_success(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    handler: IngestionHandlerProtocol,
    result: TargetSyncResult,
) -> None:
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


async def _persist_event_metadata(
    *,
    context: FullSyncContext,
    values: dict[str, object],
    error_message: str,
) -> None:
    if not await run_in_threadpool(
        _update_event_metadata_sync,
        event_id=context.event_id,
        values=values,
    ):
        raise RuntimeError(error_message)
    context.metadata.update(values)


async def _persist_sync_result(
    *,
    context: FullSyncContext,
    result: TargetSyncResult,
) -> None:
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": "validating",
            "synced_count": result.synced_count,
            "error_count": result.error_count,
        },
        error_message="failed to persist sync completion metadata",
    )


async def _persist_validation_result(
    *,
    context: FullSyncContext,
    validation_result: FullSyncValidationResult,
) -> None:
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": "validating",
            "stored_count": validation_result.stored_count,
            "missing_count": validation_result.missing_count,
            "last_validation_at": datetime.now(timezone.utc).isoformat(),
            "repair_status": (
                FullSyncRepairStatus.NOT_NEEDED.value
                if validation_result.missing_count == 0
                else validation_result.repair_status.value
            ),
        },
        error_message="failed to persist validation metadata",
    )


async def _handle_validation_success(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    handler: IngestionHandlerProtocol,
    result: TargetSyncResult,
) -> None:
    await run_in_threadpool(
        _clear_event_missing_records_sync,
        event_id=context.event_id,
    )
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": "completed",
            "repair_status": FullSyncRepairStatus.NOT_NEEDED.value,
        },
        error_message="failed to persist validation completion metadata",
    )
    await _complete_event_success(
        context=context,
        message=message,
        handler=handler,
        result=result,
    )


async def _validate_sync_result(
    *,
    context: FullSyncContext,
    validating_handler: FullSyncValidatingHandlerProtocol,
    service_cache: dict[str, object],
    expected_ids: list[str],
) -> FullSyncValidationResult:
    validation_result = await validating_handler.validate_sync_result(
        context=context,
        expected_ids=expected_ids,
        service_cache=service_cache,
    )
    await _persist_validation_result(
        context=context,
        validation_result=validation_result,
    )
    logger.info(
        "full_sync_validation_completed",
        connector=context.connector.value,
        event_id=context.event_id,
        expected_count=validation_result.expected_count,
        stored_count=validation_result.stored_count,
        missing_count=validation_result.missing_count,
    )
    return validation_result


async def _handle_validation_retry_branch(
    *,
    context: FullSyncContext,
    validation_result: FullSyncValidationResult,
    validation_ratio: float,
) -> None:
    await run_in_threadpool(
        _clear_event_missing_records_sync,
        event_id=context.event_id,
    )
    should_retry = _has_retry_attempt_remaining(context)
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": (
                "validating"
                if should_retry
                else "completed"
            ),
            "repair_status": (
                FullSyncRepairStatus.RETRYING.value
                if should_retry
                else FullSyncRepairStatus.FAILED.value
            ),
        },
        error_message="failed to persist validation retry metadata",
    )
    if should_retry:
        logger.warning(
            "full_sync_validation_retry_requested",
            connector=context.connector.value,
            event_id=context.event_id,
            expected_count=validation_result.expected_count,
            missing_count=validation_result.missing_count,
            missing_ratio=validation_ratio,
        )
        raise SyncInternalError("full_sync_validation_missing_ratio_exceeded")
    raise RuntimeError("full_sync_validation_missing_ratio_exceeded")


async def _run_revalidation(
    *,
    context: FullSyncContext,
    validating_handler: FullSyncValidatingHandlerProtocol,
    service_cache: dict[str, object],
    expected_ids: list[str],
) -> FullSyncValidationResult:
    revalidation_result = await validating_handler.validate_sync_result(
        context=context,
        expected_ids=expected_ids,
        service_cache=service_cache,
    )
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": "validating",
            "stored_count": revalidation_result.stored_count,
            "missing_count": revalidation_result.missing_count,
            "last_validation_at": datetime.now(timezone.utc).isoformat(),
        },
        error_message="failed to persist revalidation metadata",
    )
    return revalidation_result


async def _handle_revalidation_result(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    handler: IngestionHandlerProtocol,
    result: TargetSyncResult,
    revalidation_result: FullSyncValidationResult,
    skipped_count: int,
) -> None:
    logger.info(
        "full_sync_revalidation_completed",
        connector=context.connector.value,
        event_id=context.event_id,
        stored_count=revalidation_result.stored_count,
        missing_count=revalidation_result.missing_count,
        skipped_count=skipped_count,
    )

    if revalidation_result.missing_count == 0:
        await run_in_threadpool(
            _clear_event_missing_records_sync,
            event_id=context.event_id,
        )
        await _persist_event_metadata(
            context=context,
            values={
                "execution_phase": "completed",
                "repair_status": FullSyncRepairStatus.RESOLVED.value,
            },
            error_message="failed to persist repair resolved metadata",
        )
        await _complete_event_success(
            context=context,
            message=message,
            handler=handler,
            result=result,
        )
        return

    await run_in_threadpool(
        _store_event_missing_records_sync,
        event_id=context.event_id,
        missing_ids=revalidation_result.missing_ids,
    )
    should_retry = _has_retry_attempt_remaining(context)
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": (
                "repairing"
                if should_retry
                else "completed"
            ),
            "repair_status": (
                FullSyncRepairStatus.RETRYING.value
                if should_retry
                else FullSyncRepairStatus.FAILED.value
            ),
        },
        error_message="failed to persist repair unresolved metadata",
    )

    if should_retry:
        logger.warning(
            "full_sync_repair_retry_requested",
            connector=context.connector.value,
            event_id=context.event_id,
            missing_count=revalidation_result.missing_count,
            skipped_count=skipped_count,
        )
        raise SyncInternalError("full_sync_repair_unresolved")
    raise RuntimeError("full_sync_repair_unresolved")


async def _run_full_sync_repair_flow(
    *,
    context: FullSyncContext,
    validating_handler: FullSyncValidatingHandlerProtocol,
    service_cache: dict[str, object],
    validation_result: FullSyncValidationResult,
) -> int:
    await run_in_threadpool(
        _store_event_missing_records_sync,
        event_id=context.event_id,
        missing_ids=validation_result.missing_ids,
    )
    await _persist_event_metadata(
        context=context,
        values={
            "execution_phase": "repairing",
            "repair_status": FullSyncRepairStatus.REPAIRING.value,
            "last_repair_at": datetime.now(timezone.utc).isoformat(),
        },
        error_message="failed to persist repair start metadata",
    )
    logger.info(
        "full_sync_repair_started",
        connector=context.connector.value,
        event_id=context.event_id,
        missing_count=validation_result.missing_count,
    )

    repair_result = await validating_handler.repair_missing_records(
        context=context,
        validation_result=validation_result,
        service_cache=service_cache,
    )
    skipped_count = int(context.metadata.get("skipped_count") or 0) + repair_result.skipped_count
    await _persist_event_metadata(
        context=context,
        values={
            "skipped_count": skipped_count,
            "last_repair_at": datetime.now(timezone.utc).isoformat(),
        },
        error_message="failed to persist repair result metadata",
    )
    return skipped_count


async def _handle_validation_repair_branch(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    handler: IngestionHandlerProtocol,
    validating_handler: FullSyncValidatingHandlerProtocol,
    service_cache: dict[str, object],
    result: TargetSyncResult,
    validation_result: FullSyncValidationResult,
    expected_ids: list[str],
) -> None:
    skipped_count = await _run_full_sync_repair_flow(
        context=context,
        validating_handler=validating_handler,
        service_cache=service_cache,
        validation_result=validation_result,
    )
    revalidation_result = await _run_revalidation(
        context=context,
        validating_handler=validating_handler,
        service_cache=service_cache,
        expected_ids=expected_ids,
    )
    await _handle_revalidation_result(
        context=context,
        message=message,
        handler=handler,
        result=result,
        revalidation_result=revalidation_result,
        skipped_count=skipped_count,
    )


async def _run_full_sync_validation_flow(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    handler: IngestionHandlerProtocol,
    validating_handler: FullSyncValidatingHandlerProtocol,
    service_cache: dict[str, object],
    result: TargetSyncResult,
    expected_ids: list[str],
) -> None:
    logger.info(
        "full_sync_validation_started",
        connector=context.connector.value,
        event_id=context.event_id,
        synced_count=result.synced_count,
        error_count=result.error_count,
        expected_count=len(expected_ids),
    )
    await _persist_sync_result(context=context, result=result)
    validation_result = await _validate_sync_result(
        context=context,
        validating_handler=validating_handler,
        service_cache=service_cache,
        expected_ids=expected_ids,
    )

    if validation_result.missing_count == 0 or validation_result.expected_count == 0:
        await _handle_validation_success(
            context=context,
            message=message,
            handler=handler,
            result=result,
        )
        return

    validation_ratio = _missing_ratio(validation_result)
    if validation_ratio > 0.3:
        await _handle_validation_retry_branch(
            context=context,
            validation_result=validation_result,
            validation_ratio=validation_ratio,
        )
        return

    await _handle_validation_repair_branch(
        context=context,
        message=message,
        handler=handler,
        validating_handler=validating_handler,
        service_cache=service_cache,
        result=result,
        validation_result=validation_result,
        expected_ids=expected_ids,
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
                "full_sync_event_job_mismatch",
                event_id=task.event_id,
                stream_job_id=task.job_id,
            )
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="event_id and job_id mismatch",
            )
            return

        if claim.state == ClaimState.EVENT_ALREADY_TERMINAL:
            logger.warning(
                "full_sync_terminal_or_unsupported_event_skipped",
                job_id=task.job_id,
                event_id=task.event_id,
            )
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_ALREADY_TERMINAL,
                error_message="event already terminal or unsupported",
            )
            return

        if claim.state == ClaimState.EVENT_CAS_CONFLICT:
            logger.warning(
                "full_sync_event_cas_conflict",
                job_id=task.job_id,
                event_id=task.event_id,
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
        
        if not isinstance(handler, FullSyncCollectingHandlerProtocol):
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"full sync collect is not supported: connector={context.connector}, "
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
        
        identifiers = await handler.collect_identifiers(
            context=context,
            service_cache=service_cache,
        )

        await _persist_event_metadata(
            context=context,
            values={
                "expected_count": len(identifiers),
                "execution_phase": "syncing",
            },
            error_message="failed to persist collect phase result",
        )

        logger.info(
            "full_sync_identifier_collection_completed",
            connector=context.connector.value,
            event_id=context.event_id,
            expected_count=len(identifiers),
            stage=context.metadata.get("stage"),
            range_start=context.metadata.get("range_start"),
            range_end=context.metadata.get("range_end"),
        )

        result = await handler.handle(
            context=context,
            service_cache=service_cache,
        )
        validating_handler = (
            handler
            if isinstance(handler, FullSyncValidatingHandlerProtocol)
            else None
        )
        if validating_handler is None:
            await _complete_event_success(
                context=context,
                message=message,
                handler=handler,
                result=result,
            )
            return

        await _run_full_sync_validation_flow(
            context=context,
            message=message,
            handler=handler,
            validating_handler=validating_handler,
            service_cache=service_cache,
            result=result,
            expected_ids=identifiers,
        )
    except Exception as exc:
        if context is None:
            logger.exception(
                "full_sync_message_processing_failed_before_claim",
                job_id=task.job_id,
                event_id=task.event_id,
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
