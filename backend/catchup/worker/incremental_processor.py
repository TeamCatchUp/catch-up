from __future__ import annotations

import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import get_record_state
from catchup.db.incremental import transition_record_status
from catchup.db.models import IncrementalRecordStatus
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.retry_policy import resolve_retry_delay
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.incremental.error_policy import is_retryable_incremental_error
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.worker.common import deadletter
from catchup.worker.common import select_handler
from catchup.worker.schemas import ClaimResult

logger = logging.getLogger(__name__)


def _incremental_lease_until() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        seconds=max(1, int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS))
    )


def _incremental_retry_delay(exc: Exception, attempt: int) -> timedelta:
    return resolve_retry_delay(
        exc=exc,
        attempt=attempt,
        base_delay_seconds=settings.INCREMENTAL_RETRY_BASE_DELAY_SECONDS,
        max_delay_seconds=settings.INCREMENTAL_RETRY_MAX_DELAY_SECONDS,
    )


def _emit_requeue_record_audit(
    *,
    context: IncrementalSyncContext,
    next_attempt: int,
    retry_at: str,
) -> None:
    emit_audit_event(
        action=IncrementalSyncAction.RECORD,
        status=AuditStatus.SUCCESS,
        level=AuditLevel.WARNING,
        metadata=IncrementalRecordAuditMetadata.from_requeue(
            context=context,
            next_attempt=next_attempt,
            retry_at=retry_at,
        ),
    )


def _claim_incremental_task(
    task: SyncStreamTask,
    *,
    lease_owner: str,
) -> ClaimResult:
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
        )

    return ClaimResult(state=ClaimState.CLAIMED, context=context)


def _mark_incremental_success_sync(context: IncrementalSyncContext) -> bool:
    if context.record_key is None or context.generation is None:
        return False

    synced_at = datetime.now(timezone.utc)
    with SessionLocal() as db:
        return transition_record_status(
            db,
            record_key=context.record_key,
            from_statuses=[IncrementalRecordStatus.PROCESSING],
            to_status=IncrementalRecordStatus.SYNCED,
            expected_generation=context.generation,
            attempt=0,
            last_synced_at=synced_at,
        )


def _transition_incremental_failure_state_sync(
    *,
    context: IncrementalSyncContext,
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

    return transitioned


async def _handle_incremental_failure(
    *,
    context: IncrementalSyncContext,
    message: SyncStreamMessage,
    exc: Exception,
    handler: IngestionHandlerProtocol,
) -> None:
    if context.record_key is None or context.generation is None:
        await deadletter(
            message=message,
            reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
            error_message="incremental context is missing record identity",
        )
        return

    error_summary = str(exc)
    next_attempt = context.attempt + 1
    retryable = is_retryable_incremental_error(exc)

    if not retryable or next_attempt >= context.max_attempts:
        transitioned = await run_in_threadpool(
            _transition_incremental_failure_state_sync,
            context=context,
            to_status=IncrementalRecordStatus.DEAD,
            attempt=next_attempt,
            last_error=error_summary,
        )
        if not transitioned:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.RECORD_STATE_CONFLICT,
                error_message=(
                    "failed to transition incremental record state: "
                    f"record_key={context.record_key}, "
                    f"generation={context.generation}, "
                    f"to_status={IncrementalRecordStatus.DEAD.value}"
                ),
            )
            logger.error(
                "[%s][INCREMENTAL][WORKER] Record state transition failed: "
                "record_key=%s, generation=%s, to_status=%s",
                context.connector.upper(),
                context.record_key,
                context.generation,
                IncrementalRecordStatus.DEAD.value,
            )
            return

        await deadletter(
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

    next_retry_at = datetime.now(timezone.utc) + _incremental_retry_delay(
        exc, next_attempt
    )
    transitioned = await run_in_threadpool(
        _transition_incremental_failure_state_sync,
        context=context,
        to_status=IncrementalRecordStatus.RETRY_WAIT,
        attempt=next_attempt,
        next_retry_at=next_retry_at,
        last_error=error_summary,
    )
    if not transitioned:
        await deadletter(
            message=message,
            reason=SyncStreamFailureReason.RECORD_STATE_CONFLICT,
            error_message=(
                "failed to transition incremental record state: "
                f"record_key={context.record_key}, "
                f"generation={context.generation}, "
                f"to_status={IncrementalRecordStatus.RETRY_WAIT.value}"
            ),
        )
        logger.error(
            "[%s][INCREMENTAL][WORKER] Record state transition failed: "
            "record_key=%s, generation=%s, to_status=%s",
            context.connector.upper(),
            context.record_key,
            context.generation,
            IncrementalRecordStatus.RETRY_WAIT.value,
        )
        return

    await handler.on_target_requeued(
        context=context,
        next_attempt=next_attempt,
        error_summary=error_summary,
    )
    _emit_requeue_record_audit(
        context=context,
        next_attempt=next_attempt,
        retry_at=next_retry_at.isoformat(),
    )


async def process_incremental_message(
    message: SyncStreamMessage,
    service_cache: dict[str, object],
    *,
    lease_owner: str,
) -> None:
    task = message.task
    context: IncrementalSyncContext | None = None
    handler: IngestionHandlerProtocol | None = None

    try:
        claim = await run_in_threadpool(
            _claim_incremental_task,
            task,
            lease_owner=lease_owner,
        )
        if claim.state == ClaimState.INVALID_INCREMENTAL_TASK:
            await deadletter(
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
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected empty incremental claim context",
            )
            return
        if not isinstance(context, IncrementalSyncContext):
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
                error_message="unexpected incremental claim context type",
            )
            return

        handler = select_handler(context)
        if handler is None:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
                error_message=(
                    f"unsupported incremental handler: connector={context.connector}, "
                    f"sync_type={context.sync_type}"
                ),
            )
            return

        await handler.on_target_started(context=context)

        result = await handler.handle(
            context=context,
            service_cache=service_cache,
        )
        if not await run_in_threadpool(
            _mark_incremental_success_sync,
            context,
        ):
            logger.warning(
                "[INCREMENTAL][WORKER] Success transition skipped: record_key=%s, generation=%s",
                context.record_key,
                context.generation,
            )
            return

        await handler.on_target_completed(context=context, result=result)
    except Exception as exc:
        if context is None:
            logger.exception(
                "[INCREMENTAL][WORKER] Message processing failed before claim: record_key=%s, generation=%s",
                task.record_key,
                task.generation,
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
