from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import (
    get_record_state,
    list_parent_cohort_records,
    mark_parent_cohort_synced,
    transition_record_status,
)
from catchup.db.models import (
    IncrementalRecordStatus,
    SyncConnector,
    SyncEventStatus,
    SyncJobStatus,
    SyncType,
)
from catchup.db.sync import (
    claim_event_for_processing,
    complete_job_failed,
    complete_job_success,
    get_event,
    get_job,
    list_events_by_job,
    mark_event_failed,
    mark_event_retrying,
    mark_event_success,
    requeue_retrying_event,
    start_job,
)
from catchup.sync.common.protocols import IngestionHandlerProtocol, WorkerProtocol
from catchup.sync.common.schemas import (
    ClaimState,
    FullSyncContext,
    IncrementalSyncContext,
    SyncContext,
    SyncStreamMessage,
    SyncStreamTask,
)
from catchup.sync.incremental.error_policy import is_retryable_incremental_error
from catchup.sync.stream_runtime.stream_constants import (
    STREAM_CLAIM_START_ID,
    SyncStreamFailureReason,
)
from catchup.sync.stream_runtime.stream_queue import publish_deadletter
from catchup.sync.stream_runtime.sync_runtime import (
    ack_consumed_messages,
    initialize_stream_runtime,
    publish_job_events,
    read_ready_messages,
)
from catchup.sync.status_stream.pubsub import publish_job_status_event
from catchup.sync.status_stream.schemas import (
    SyncStatusEventType,
    SyncStatusStreamEvent,
    utc_now_iso,
)
from catchup.sync.sync_audit import (
    emit_worker_job_completed,
    emit_worker_job_failed,
    emit_worker_job_started,
    emit_worker_target_completed,
    emit_worker_target_failed,
    emit_worker_target_requeued,
    emit_worker_target_started,
)
from catchup.worker.handlers import get_ingestion_handler

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClaimResult:
    state: ClaimState
    context: SyncContext | None = None
    job_started: bool = False
    total_targets: int = 0


def _consumer_name() -> str:
    return f"sync-worker-{uuid4().hex[:8]}"


def _incremental_lease_until() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        seconds=max(1, int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS))
    )


def _task_fields(task: SyncStreamTask) -> dict[str, str]:
    return task.to_stream_fields()


def _task_lock_key(task: SyncStreamTask) -> tuple[str, str, str, str]:
    target_type = (task.target_type or "").strip() or ("record" if task.record_key else "event")
    target_id = (
        (task.target_id or "").strip()
        or (task.record_key or "").strip()
        or task.event_id
    )
    return (
        task.connector.strip(),
        (task.scope_id or "").strip(),
        target_type,
        target_id,
    )


def _select_handler(context: SyncContext) -> IngestionHandlerProtocol | None:
    return get_ingestion_handler(
        connector=context.connector,
        sync_type=context.sync_type,
    )


def _build_target_status_event(
    *,
    context: SyncContext,
    event_type: SyncStatusEventType,
    status: str,
    attempt: int | None = None,
    extra_payload: dict[str, object] | None = None,
) -> SyncStatusStreamEvent:
    payload: dict[str, object] = {
        "sync_type": context.sync_type,
        "event_id": context.event_id,
        "target_type": context.target_type,
        "target_id": context.target_id,
        "target_name": context.target_name,
        "status": status,
        "attempt": context.attempt if attempt is None else attempt,
        "max_attempts": context.max_attempts,
    }
    if extra_payload:
        payload.update(extra_payload)

    return SyncStatusStreamEvent(
        connector=context.connector,
        job_id=context.job_id,
        scope_id=context.scope_id,
        event_type=event_type,
        timestamp=utc_now_iso(),
        payload=payload,
    )


def _build_job_status_event(
    *,
    context: FullSyncContext,
    event_type: SyncStatusEventType,
    status: str,
    total_targets: int,
    completed_targets: int | None = None,
    failed_targets: int | None = None,
    requeued_targets: int | None = None,
) -> SyncStatusStreamEvent:
    # Job 집계 상태는 terminal/started 이벤트에서만 별도 payload로 발행
    payload: dict[str, object] = {
        "sync_type": context.sync_type,
        "status": status,
        "total_targets": total_targets,
    }
    if completed_targets is not None:
        payload["completed_targets"] = completed_targets
    if failed_targets is not None:
        payload["failed_targets"] = failed_targets
    if requeued_targets is not None:
        payload["requeued_targets"] = requeued_targets

    return SyncStatusStreamEvent(
        connector=context.connector,
        job_id=context.job_id,
        scope_id=context.scope_id,
        event_type=event_type,
        timestamp=utc_now_iso(),
        payload=payload,
    )


async def _publish_status_event(event: SyncStatusStreamEvent) -> None:
    # Status stream publish 실패 : 스트리밍을 끊지 않고 로깅만 남김
    try:
        await publish_job_status_event(event)
    except Exception as exc:
        logger.warning(
            "[SYNC][STATUS][WORKER] Failed to publish status event: job_id=%s, event_type=%s, error=%s",
            event.job_id,
            event.event_type.value,
            exc,
            exc_info=True,
        )


async def _deadletter(
    *,
    message: SyncStreamMessage,
    reason: SyncStreamFailureReason,
    error_message: str | None,
) -> None:
    await publish_deadletter(
        reason=reason,
        message_id=message.message_id,
        fields=_task_fields(message.task),
        error_message=error_message,
    )


def _claim_event(task: SyncStreamTask) -> ClaimResult:
    with SessionLocal() as db:
        event = get_event(db, task.event_id)
        if event is None:
            return ClaimResult(state=ClaimState.EVENT_NOT_FOUND)

        if event.job_id != task.job_id:
            return ClaimResult(state=ClaimState.EVENT_JOB_MISMATCH)

        if event.status in {SyncEventStatus.SUCCESS, SyncEventStatus.FAILED}:
            return ClaimResult(state=ClaimState.EVENT_ALREADY_TERMINAL)

        if event.status == SyncEventStatus.RETRYING:
            if not requeue_retrying_event(db, task.event_id):
                return ClaimResult(state=ClaimState.EVENT_CAS_CONFLICT)

        if not claim_event_for_processing(db, task.event_id):
            return ClaimResult(state=ClaimState.EVENT_CAS_CONFLICT)

        claimed = get_event(db, task.event_id)
        if claimed is None:
            return ClaimResult(state=ClaimState.EVENT_NOT_FOUND)

        job = get_job(db, task.job_id)
        if job is None:
            return ClaimResult(state=ClaimState.JOB_NOT_FOUND)

        metadata = (
            claimed.resource_metadata
            if isinstance(claimed.resource_metadata, dict)
            else {}
        )
        scope_id = str(metadata.get("scope_id") or job.scope_id)
        target_id = str(claimed.resource_id)
        context = FullSyncContext(
            event_id=claimed.event_id,
            job_id=claimed.job_id,
            connector=claimed.connector,
            scope_id=scope_id,
            target_type=claimed.resource_type,
            target_id=target_id,
            target_name=str(metadata.get("target_name") or target_id),
            sync_from=(
                str(metadata.get("sync_from"))
                if metadata.get("sync_from") is not None
                else None
            ),
            attempt=int(claimed.attempt),
            max_attempts=int(claimed.max_attempts),
            metadata=metadata,
        )

        job_started = start_job(db, task.job_id)
        total_targets = 0
        if job_started:
            total_targets = len(list_events_by_job(db, job_id=task.job_id, limit=100000))

    return ClaimResult(
        state=ClaimState.CLAIMED,
        context=context,
        job_started=job_started,
        total_targets=total_targets,
    )


def _claim_incremental_task(task: SyncStreamTask, *, lease_owner: str) -> ClaimResult:
    record_key = (task.record_key or "").strip()
    if not record_key or task.generation is None:
        return ClaimResult(state=ClaimState.INVALID_INCREMENTAL_TASK)

    with SessionLocal() as db:
        record = get_record_state(db, record_key)
        if record is None:
            return ClaimResult(state=ClaimState.RECORD_NOT_FOUND)

        if record.generation != task.generation:
            return ClaimResult(state=ClaimState.STALE_TASK)

        if record.status != IncrementalRecordStatus.QUEUED:
            return ClaimResult(state=ClaimState.STALE_TASK)

        if not transition_record_status(
            db,
            record_key=record_key,
            from_statuses=[IncrementalRecordStatus.QUEUED],
            to_status=IncrementalRecordStatus.PROCESSING,
            expected_generation=task.generation,
            processing_generation=task.generation,
            lease_owner=lease_owner,
            lease_until=_incremental_lease_until(),
        ):
            return ClaimResult(state=ClaimState.RECORD_CAS_CONFLICT)

        claimed = get_record_state(db, record_key)
        if claimed is None:
            return ClaimResult(state=ClaimState.RECORD_NOT_FOUND)

        cohort = list_parent_cohort_records(
            db,
            connector=claimed.connector,
            scope_id=claimed.scope_id,
            parent_type=claimed.parent_type,
            parent_id=claimed.parent_id,
            max_generation=claimed.generation,
        )
        batch_sync_from = claimed.last_event_at.isoformat()
        batch_generation_ceiling = claimed.generation
        if cohort:
            batch_sync_from = min(item.last_event_at for item in cohort).isoformat()
            batch_generation_ceiling = max(item.generation for item in cohort)

        context = IncrementalSyncContext(
            event_id=task.event_id,
            job_id=task.job_id,
            connector=task.connector,
            scope_id=claimed.scope_id,
            target_type=claimed.parent_type,
            target_id=claimed.parent_id,
            target_name=claimed.parent_id,
            attempt=int(claimed.attempt),
            max_attempts=max(1, int(settings.INCREMENTAL_MAX_ATTEMPTS)),
            record_key=claimed.record_key,
            generation=claimed.generation,
            record_type=claimed.record_type,
            record_id=claimed.record_id,
            parent_type=claimed.parent_type,
            parent_id=claimed.parent_id,
            event_kind=claimed.event_kind,
            last_event_at=claimed.last_event_at.isoformat(),
            batch_sync_from=batch_sync_from,
            batch_generation_ceiling=batch_generation_ceiling,
        )

    return ClaimResult(state=ClaimState.CLAIMED, context=context)


async def _mark_event_success(context: FullSyncContext) -> bool:
    with SessionLocal() as db:
        return mark_event_success(db, event_id=context.event_id)


def _incremental_retry_delay(attempt: int) -> timedelta:
    base = max(1.0, float(settings.INCREMENTAL_RETRY_BASE_DELAY_SECONDS))
    max_delay = max(base, float(settings.INCREMENTAL_RETRY_MAX_DELAY_SECONDS))
    seconds = min(max_delay, base * (2 ** max(0, attempt - 1)))
    return timedelta(seconds=seconds)


async def _mark_incremental_success(context: IncrementalSyncContext) -> bool:
    if context.record_key is None or context.generation is None:
        return False

    synced_at = datetime.now(timezone.utc)
    with SessionLocal() as db:
        if (
            context.parent_type
            and context.parent_id
            and context.batch_generation_ceiling is not None
        ):
            updated = mark_parent_cohort_synced(
                db,
                connector=SyncConnector(context.connector),
                scope_id=context.scope_id,
                parent_type=context.parent_type,
                parent_id=context.parent_id,
                max_generation=context.batch_generation_ceiling,
                last_synced_at=synced_at,
            )
            return updated >= 1

        return transition_record_status(
            db,
            record_key=context.record_key,
            from_statuses=[IncrementalRecordStatus.PROCESSING],
            to_status=IncrementalRecordStatus.SYNCED,
            expected_generation=context.generation,
            attempt=0,
            last_synced_at=synced_at,
        )

async def _transition_incremental_failure_state(
    *,
    context: IncrementalSyncContext,
    message: SyncStreamMessage,
    to_status: IncrementalRecordStatus,
    attempt: int,
    last_error: str,
    next_retry_at: datetime | None = None,
) -> bool:
    if context.record_key is None or context.generation is None:
        return False
    
    with SessionLocal() as db:
        transitioned = transition_record_status(
            db,
            record_key=context.record_key,
            from_statuses=[IncrementalRecordStatus.PROCESSING],
            to_status=to_status,
            expected_generation=context.generation,
            attempt=attempt,
            next_retry_at=next_retry_at,
            last_error=last_error,
        )
    
    if transitioned:
        return True
    
    await _deadletter(
        message=message,
        reason=SyncStreamFailureReason.RECORD_STATE_CONFLICT,
        error_message=(
            "failed to transition incremental record state: "
            f"record_key={context.record_key}, "
            f"generation={context.generation}, "
            f"to_status={to_status.value}"
        ),
    )
    logger.error(
        "[%s][INCREMENTAL][WORKER] Record state transition failed: "
        "record_key=%s, generation=%s, to_status=%s",
        context.connector.upper(),
        context.record_key,
        context.generation,
        to_status.value,
    )
    return False



async def _handle_incremental_failure(
    *,
    context: IncrementalSyncContext,
    message: SyncStreamMessage,
    exc: Exception,
    handler: IngestionHandlerProtocol,
) -> None:
    if context.record_key is None or context.generation is None:
        await _deadletter(
            message=message,
            reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
            error_message="incremental context is missing record identity",
        )
        return

    error_summary = str(exc)
    next_attempt = context.attempt + 1
    retryable = is_retryable_incremental_error(exc)

    if not retryable or next_attempt >= context.max_attempts:
        transitioned = await _transition_incremental_failure_state(
            context=context,
            message=message,
            to_status=IncrementalRecordStatus.DEAD,
            attempt=next_attempt,
            last_error=error_summary,
        )
        if not transitioned:
            return

        await _deadletter(
            message=message,
            reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
            error_message=error_summary,
        )
        await handler.on_target_failed(
            context=context,
            next_attempt=next_attempt,
            error_summary=error_summary,
            retryable=retryable,
        )
        logger.error(
            "[%s][INCREMENTAL][WORKER] Record dead: record_key=%s, attempt=%s, retryable=%s, error=%s",
            context.connector.upper(),
            context.record_key,
            next_attempt,
            retryable,
            error_summary,
        )
        return

    next_retry_at = datetime.now(timezone.utc) + _incremental_retry_delay(next_attempt)
    transitioned = await _transition_incremental_failure_state(
        context=context,
        message=message,
        to_status=IncrementalRecordStatus.RETRY_WAIT,
        attempt=next_attempt,
        next_retry_at=next_retry_at,
        last_error=error_summary,
    )
    if not transitioned:
        return

    await handler.on_target_requeued(
        context=context,
        next_attempt=next_attempt,
        error_summary=error_summary,
    )
    logger.warning(
        "[%s][INCREMENTAL][WORKER] Record retry scheduled: record_key=%s, next_attempt=%s, retry_at=%s, error=%s",
        context.connector.upper(),
        context.record_key,
        next_attempt,
        next_retry_at.isoformat(),
        error_summary,
    )


async def _handle_event_failure(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    exc: Exception,
    handler: IngestionHandlerProtocol,
) -> None:
    error_summary = str(exc)
    next_attempt = context.attempt + 1

    if next_attempt >= context.max_attempts:
        with SessionLocal() as db:
            if not mark_event_failed(db, context.event_id):
                await _deadletter(
                    message=message,
                    reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                    error_message="failed to transition event to FAILED",
                )
                return

        await _publish_status_event(
            _build_target_status_event(
                context=context,
                event_type=SyncStatusEventType.TARGET_FAILED,
                status=SyncEventStatus.FAILED.value,
                attempt=next_attempt,
            )
        )

        await _deadletter(
            message=message,
            reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
            error_message=error_summary,
        )
        await handler.on_target_failed(
            context=context,
            next_attempt=next_attempt,
            error_summary=error_summary,
            retryable=False,
        )
        emit_worker_target_failed(
            connector=context.connector,
            sync_type=context.sync_type,
            run_id=context.job_id,
            scope_id=context.scope_id,
            target_type=context.target_type,
            target_id=context.target_id,
            target_name=context.target_name,
            failure_reason="max_retries_exceeded",
            error_summary=error_summary,
            attempt=next_attempt,
            retryable=False,
        )
        logger.error(
            "[%s][%s][WORKER] Event failed: job_id=%s, event_id=%s, attempt=%s, max_attempts=%s, error=%s",
            context.connector.upper(),
            context.sync_type.upper(),
            context.job_id,
            context.event_id,
            next_attempt,
            context.max_attempts,
            error_summary,
        )
        return

    with SessionLocal() as db:
        if not mark_event_retrying(db, context.event_id):
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="failed to transition IN_PROGRESS -> RETRYING",
            )
            return

        if not requeue_retrying_event(db, context.event_id):
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="failed to transition RETRYING -> PENDING",
            )
            return

    await publish_job_events(
        job_id=context.job_id,
        event_ids=[context.event_id],
        connector=context.connector,
        sync_type=context.sync_type,
        scope_id=context.scope_id,
        target_type=context.target_type,
        target_ids=[context.target_id],
        max_attempts=context.max_attempts,
    )
    await _publish_status_event(
        _build_target_status_event(
            context=context,
            event_type=SyncStatusEventType.TARGET_REQUEUED,
            status=SyncEventStatus.PENDING.value,
            attempt=next_attempt,
            extra_payload={"error_summary": error_summary},
        )
    )
    await handler.on_target_requeued(
        context=context,
        next_attempt=next_attempt,
        error_summary=error_summary,
    )
    emit_worker_target_requeued(
        connector=context.connector,
        sync_type=context.sync_type,
        run_id=context.job_id,
        scope_id=context.scope_id,
        target_type=context.target_type,
        target_id=context.target_id,
        target_name=context.target_name,
        next_attempt=next_attempt,
        error_summary=error_summary,
    )
    logger.warning(
        "[%s][%s][WORKER] Event requeued: job_id=%s, event_id=%s, attempt=%s, error=%s",
        context.connector.upper(),
        context.sync_type.upper(),
        context.job_id,
        context.event_id,
        next_attempt,
        error_summary,
    )


async def _finalize_job_if_done(
    context: FullSyncContext,
    handler: IngestionHandlerProtocol,
) -> None:
    if context.sync_type != SyncType.FULL:
        return

    job_id = context.job_id

    with SessionLocal() as db:
        job = get_job(db, job_id)
        if job is None:
            return

        if job.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
            return

        events = list_events_by_job(db, job_id=job_id, limit=100000)
        if not events:
            return

        if any(
            event.status
            in {
                SyncEventStatus.PENDING,
                SyncEventStatus.IN_PROGRESS,
                SyncEventStatus.RETRYING,
            }
            for event in events
        ):
            return

        total_targets = len(events)
        completed_targets = sum(
            1 for event in events if event.status == SyncEventStatus.SUCCESS
        )
        failed_targets = sum(
            1 for event in events if event.status == SyncEventStatus.FAILED
        )
        requeued_targets = sum(int(event.attempt) for event in events)

        if failed_targets == 0:
            if not complete_job_success(db, job_id):
                return
            # 모든 target 처리 이후에 최종 집계를 포함한 job 완료 이벤트를 발행
            await _publish_status_event(
                _build_job_status_event(
                    context=context,
                    event_type=SyncStatusEventType.JOB_COMPLETED,
                    status=SyncJobStatus.SUCCESS.value,
                    total_targets=total_targets,
                    completed_targets=completed_targets,
                    failed_targets=failed_targets,
                    requeued_targets=requeued_targets,
                )
            )
            await handler.on_job_completed(
                context=context,
                total_targets=total_targets,
                completed_targets=completed_targets,
                failed_targets=failed_targets,
                requeued_targets=requeued_targets,
            )
            emit_worker_job_completed(
                connector=context.connector,
                sync_type=context.sync_type,
                run_id=context.job_id,
                scope_id=context.scope_id,
                total_targets=total_targets,
                completed_targets=completed_targets,
                failed_targets=failed_targets,
                requeued_targets=requeued_targets,
                synced_records=0,
            )
            return

        if not complete_job_failed(db, job_id):
            return
        # 실패가 남은 채 완료된 경우 Job 실패 이벤트를 발행한다
        await _publish_status_event(
            _build_job_status_event(
                context=context,
                event_type=SyncStatusEventType.JOB_FAILED,
                status=SyncJobStatus.FAILED.value,
                total_targets=total_targets,
                completed_targets=completed_targets,
                failed_targets=failed_targets,
                requeued_targets=requeued_targets,
            )
        )
        await handler.on_job_failed(
            context=context,
            total_targets=total_targets,
            failed_targets=failed_targets,
        )
        emit_worker_job_failed(
            connector=context.connector,
            sync_type=context.sync_type,
            run_id=context.job_id,
            scope_id=context.scope_id,
            failure_reason="event_failures_remaining",
            error_summary=f"failed_events={failed_targets}, total_events={total_targets}",
        )


async def _process_incremental_message(
    message: SyncStreamMessage,
    service_cache: dict[str, object],
    *,
    lease_owner: str,
) -> None:
    task = message.task
    context: IncrementalSyncContext | None = None
    handler: IngestionHandlerProtocol | None = None

    try:
        claim = _claim_incremental_task(task, lease_owner=lease_owner)
        if claim.state == ClaimState.INVALID_INCREMENTAL_TASK:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.INVALID_STREAM_PAYLOAD,
                error_message="incremental stream payload is missing record metadata",
            )
            return

        if claim.state == ClaimState.RECORD_NOT_FOUND:
            logger.warning(
                "[INCREMENTAL][WORKER] Record not found: record_key=%s, generation=%s",
                task.record_key,
                task.generation,
            )
            return

        if claim.state in {ClaimState.STALE_TASK, ClaimState.RECORD_CAS_CONFLICT}:
            logger.info(
                "[INCREMENTAL][WORKER] Stale task skipped: record_key=%s, generation=%s, state=%s",
                task.record_key,
                task.generation,
                claim.state,
            )
            return

        context = claim.context
        if context is None:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected empty incremental claim context",
            )
            return
        if not isinstance(context, IncrementalSyncContext):
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected incremental claim context type",
            )
            return

        handler = _select_handler(context)
        if handler is None:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"unsupported incremental handler: connector={context.connector}, "
                    f"sync_type={context.sync_type}"
                ),
            )
            return

        result = await handler.handle(
            context=context,
            service_cache=service_cache,
        )
        if not await _mark_incremental_success(context):
            logger.warning(
                "[INCREMENTAL][WORKER] Success transition skipped: record_key=%s, generation=%s",
                context.record_key,
                context.generation,
            )
            return

        emit_worker_target_completed(
            connector=context.connector,
            sync_type=context.sync_type,
            run_id=context.job_id,
            scope_id=context.scope_id,
            target_type=context.target_type,
            target_id=context.target_id,
            target_name=context.target_name,
            synced_count=result.synced_count,
            error_count=result.error_count,
            skipped=result.skipped,
        )
        await handler.on_target_completed(context=context, result=result)
        logger.info(
            "[%s][INCREMENTAL][WORKER] Record synced: record_key=%s, generation=%s, synced=%s, errors=%s",
            context.connector.upper(),
            context.record_key,
            context.generation,
            result.synced_count,
            result.error_count,
        )
    except Exception as exc:
        if context is None:
            logger.exception(
                "[INCREMENTAL][WORKER] Message processing failed before claim: record_key=%s, generation=%s",
                task.record_key,
                task.generation,
            )
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message=str(exc),
            )
            return

        if handler is None:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"unsupported incremental handler: connector={context.connector}, "
                    f"sync_type={context.sync_type}"
                ),
            )
            return

        await _handle_incremental_failure(
            context=context,
            message=message,
            exc=exc,
            handler=handler,
        )
    finally:
        try:
            await ack_consumed_messages([message])
        except Exception:
            logger.exception(
                "[INCREMENTAL][WORKER] Message ack failed: record_key=%s, generation=%s, message_id=%s",
                task.record_key,
                task.generation,
                message.message_id,
            )


async def _process_message(
    message: SyncStreamMessage,
    service_cache: dict[str, object],
    *,
    lease_owner: str,
) -> None:
    task = message.task
    if task.sync_type == SyncType.INCREMENTAL:
        await _process_incremental_message(
            message,
            service_cache,
            lease_owner=lease_owner,
        )
        return

    context: FullSyncContext | None = None
    handler: IngestionHandlerProtocol | None = None

    try:
        claim = _claim_event(task)

        if claim.state == ClaimState.EVENT_NOT_FOUND:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_NOT_FOUND,
                error_message="sync event not found",
            )
            return

        if claim.state == ClaimState.JOB_NOT_FOUND:
            await _deadletter(
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
            await _deadletter(
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
            await _deadletter(
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
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="event status transition CAS conflict",
            )
            return

        context = claim.context
        if context is None:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected empty claim context",
            )
            return
        if not isinstance(context, FullSyncContext):
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected full sync claim context type",
            )
            return

        handler = _select_handler(context)
        if handler is None:
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"unsupported handler: connector={context.connector}, "
                    f"sync_type={context.sync_type}"
                ),
            )
            return

        if claim.job_started:
            # 첫 target claim으로 job이 시작된 경우에만 1회 발행
            await _publish_status_event(
                _build_job_status_event(
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
            emit_worker_job_started(
                connector=context.connector,
                sync_type=context.sync_type,
                run_id=context.job_id,
                scope_id=context.scope_id,
                total_targets=claim.total_targets,
            )

        # target claim 성공 이후, 실제 처리 시점에 스트리밍
        await _publish_status_event(
            _build_target_status_event(
                context=context,
                event_type=SyncStatusEventType.TARGET_STARTED,
                status=SyncEventStatus.IN_PROGRESS.value,
            )
        )
        await handler.on_target_started(context=context)
        emit_worker_target_started(
            connector=context.connector,
            sync_type=context.sync_type,
            run_id=context.job_id,
            scope_id=context.scope_id,
            target_type=context.target_type,
            target_id=context.target_id,
            target_name=context.target_name,
            attempt=context.attempt,
        )

        result = await handler.handle(
            context=context,
            service_cache=service_cache,
        )
        if not await _mark_event_success(context):
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="failed to transition event to SUCCESS",
            )
            return

        await _publish_status_event(
            _build_target_status_event(
                context=context,
                event_type=SyncStatusEventType.TARGET_COMPLETED,
                status=SyncEventStatus.SUCCESS.value,
            )
        )
        await handler.on_target_completed(context=context, result=result)

        emit_worker_target_completed(
            connector=context.connector,
            sync_type=context.sync_type,
            run_id=context.job_id,
            scope_id=context.scope_id,
            target_type=context.target_type,
            target_id=context.target_id,
            target_name=context.target_name,
            synced_count=result.synced_count,
            error_count=result.error_count,
            skipped=result.skipped,
        )
    except Exception as exc:
        if context is None:
            logger.exception(
                "[SYNC][WORKER] Message processing failed before claim: job_id=%s, event_id=%s",
                task.job_id,
                task.event_id,
            )
            await _deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message=str(exc),
            )
            return

        if handler is None:
            await _deadletter(
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
            await ack_consumed_messages([message])
        except Exception:
            logger.exception(
                "[SYNC][WORKER] Message ack failed: job_id=%s, event_id=%s, message_id=%s",
                task.job_id,
                task.event_id,
                message.message_id,
            )

        if context is not None and handler is not None:
            await _finalize_job_if_done(context, handler)


class SyncWorker(WorkerProtocol):
    def __init__(self) -> None:
        self._service_cache: dict[str, object] = {}
        self._target_locks: dict[tuple[str, str, str, str], asyncio.Lock] = {}
        self._parallelism = max(1, int(settings.SYNC_WORKER_CHANNEL_CONCURRENCY))
        self._semaphore = asyncio.Semaphore(self._parallelism)
        self._consumer = ""

    async def process(self, message: SyncStreamMessage) -> None:
        lock_key = _task_lock_key(message.task)
        lock = self._target_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            async with self._semaphore:
                await _process_message(
                    message,
                    self._service_cache,
                    lease_owner=self._consumer,
                )

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        consumer = _consumer_name()
        reclaim_start_id = STREAM_CLAIM_START_ID
        self._service_cache = {}
        self._consumer = consumer
        self._target_locks = {}
        self._parallelism = max(1, int(settings.SYNC_WORKER_CHANNEL_CONCURRENCY))
        self._semaphore = asyncio.Semaphore(self._parallelism)

        await initialize_stream_runtime()
        logger.info("[SYNC][WORKER] Worker started: consumer=%s", consumer)

        while not stop_event.is_set():
            try:
                messages, reclaim_start_id = await read_ready_messages(
                    consumer_name=consumer,
                    reclaim_min_idle_ms=max(
                        1, int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS * 1000)
                    ),
                    reclaim_start_id=reclaim_start_id,
                    reclaim_count=max(
                        1, settings.SYNC_WORKER_CHANNEL_CONCURRENCY * 10
                    ),
                    read_count=max(1, settings.SYNC_WORKER_CHANNEL_CONCURRENCY),
                    block_ms=max(0, settings.SYNC_QUEUE_BLOCK_TIMEOUT_SECONDS * 1000),
                )

                if not messages:
                    await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)
                    continue

                tasks = [
                    asyncio.create_task(self.process(message))
                    for message in messages
                    if not stop_event.is_set()
                ]
                if not tasks:
                    continue

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.exception(
                            "[SYNC][WORKER] Worker task failed",
                            exc_info=result,
                        )

            except Exception:
                logger.exception("[SYNC][WORKER] Worker loop error")
                await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)

        logger.info("[SYNC][WORKER] Worker stopped: consumer=%s", consumer)


_sync_worker = SyncWorker()


async def run_forever(stop_event: asyncio.Event) -> None:
    await _sync_worker.run_forever(stop_event)
