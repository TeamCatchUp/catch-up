from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool
import structlog

from catchup.audit.actions import FullSyncAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.metadata import FullSyncJobAuditMetadata
from catchup.configs.config import settings
from catchup.db.models import SyncJobStatus
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.retry_policy import is_retryable_sync_error
from catchup.sync.common.retry_policy import resolve_retry_delay
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.worker.common import deadletter
from catchup.worker.common import select_handler
from catchup.worker.full import claim_event
from catchup.worker.full import finalize_job_if_done_sync
from catchup.worker.full import mark_event_failed_sync
from catchup.worker.full import mark_event_success_sync
from catchup.worker.full import schedule_event_retry_sync

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ClaimedFullSync:
    context: FullSyncContext
    job_started: bool
    total_targets: int


async def process_full_sync_message(
    message: SyncStreamMessage,
    service_cache: dict[str, object],
) -> None:
    task_log = create_task_log(message)
    context: FullSyncContext | None = None
    handler: IngestionHandlerProtocol | None = None

    try:
        claimed = await _claim_full_sync(message, task_log)
        if claimed is None:
            return

        context = claimed.context
        handler = await _select_full_sync_handler(
            message=message,
            context=context,
        )
        if handler is None:
            return

        await _process_target(
            message=message,
            claimed=claimed,
            handler=handler,
            service_cache=service_cache,
        )
    except Exception as exc:
        await _handle_processing_exception(
            message=message,
            task_log=task_log,
            context=context,
            handler=handler,
            exc=exc,
        )
    finally:
        if context is not None and handler is not None:
            await _finalize_job_if_done(context, handler)


async def _claim_full_sync(
    message: SyncStreamMessage,
    task_log: structlog.typing.FilteringBoundLogger,
) -> ClaimedFullSync | None:
    claim = await run_in_threadpool(claim_event, message.task)
    if claim.state != ClaimState.CLAIMED:
        await _deadletter_claim_failure(
            message=message,
            task_log=task_log,
            state=claim.state,
        )
        return None

    context = claim.context
    if context is None:
        await deadletter(
            message=message,
            reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
            error_message="unexpected empty claim context",
        )
        task_log.error("full_sync_claim_context_missing")
        return None

    if not isinstance(context, FullSyncContext):
        await deadletter(
            message=message,
            reason=SyncStreamFailureReason.PROCESSING_EXCEPTION,
            error_message="unexpected full sync claim context type",
        )
        task_log.error(
            "full_sync_claim_context_invalid",
            context_type=type(context).__name__,
        )
        return None

    return ClaimedFullSync(
        context=context,
        job_started=claim.job_started,
        total_targets=claim.total_targets,
    )


async def _select_full_sync_handler(
    *,
    message: SyncStreamMessage,
    context: FullSyncContext,
) -> IngestionHandlerProtocol | None:
    handler = select_handler(context)
    if handler is not None:
        return handler

    await deadletter(
        message=message,
        reason=SyncStreamFailureReason.UNSUPPORTED_HANDLER,
        error_message=_unsupported_handler_error(context),
    )
    create_context_log(context).error("full_sync_handler_missing")
    return None


async def _process_target(
    *,
    message: SyncStreamMessage,
    claimed: ClaimedFullSync,
    handler: IngestionHandlerProtocol,
    service_cache: dict[str, object],
) -> None:
    context = claimed.context
    context_log = create_context_log(context)

    await _notify_job_started(claimed=claimed, handler=handler)
    await handler.on_target_started(context=context)

    result = await handler.handle(
        context=context,
        service_cache=service_cache,
    )
    if not await run_in_threadpool(mark_event_success_sync, context):
        await deadletter(
            message=message,
            reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
            error_message="failed to transition event to SUCCESS",
        )
        context_log.error("full_sync_success_transition_conflict")
        return

    await handler.on_target_completed(context=context, result=result)
    context_log.info(
        "full_sync_target_completed",
        synced_count=result.synced_count,
        error_count=result.error_count,
        skipped=result.skipped,
    )


async def _notify_job_started(
    *,
    claimed: ClaimedFullSync,
    handler: IngestionHandlerProtocol,
) -> None:
    if not claimed.job_started:
        return

    await handler.on_job_started(
        context=claimed.context,
        total_targets=claimed.total_targets,
    )
    _emit_job_audit(
        status=AuditStatus.ATTEMPT,
        metadata=FullSyncJobAuditMetadata.from_job_start(
            context=claimed.context,
            total_targets=claimed.total_targets,
        ),
    )


async def _handle_processing_exception(
    *,
    message: SyncStreamMessage,
    task_log: structlog.typing.FilteringBoundLogger,
    context: FullSyncContext | None,
    handler: IngestionHandlerProtocol | None,
    exc: Exception,
) -> None:
    if context is None:
        task_log.exception(
            "full_sync_pre_claim_processing_failed",
            error_summary=str(exc),
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
            error_message=_unsupported_handler_error(context),
        )
        create_context_log(context).error("full_sync_handler_missing")
        return

    await _handle_event_failure(
        context=context,
        message=message,
        exc=exc,
        handler=handler,
    )


async def _handle_event_failure(
    *,
    context: FullSyncContext,
    message: SyncStreamMessage,
    exc: Exception,
    handler: IngestionHandlerProtocol,
) -> None:
    context_log = create_context_log(context)
    error_summary = str(exc)
    next_attempt = context.attempt + 1
    retryable = is_retryable_sync_error(exc)
    should_retry = retryable and next_attempt < context.max_attempts

    if should_retry:
        retry_delay = _full_sync_retry_delay(exc, next_attempt)
        next_retry_at = datetime.now(timezone.utc) + retry_delay
        scheduled = await run_in_threadpool(
            schedule_event_retry_sync,
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
            context_log.error(
                "full_sync_retry_transition_conflict",
                next_attempt=next_attempt,
                error_summary=error_summary,
            )
            return

        await handler.on_target_requeued(
            context=context,
            next_attempt=next_attempt,
            error_summary=error_summary,
        )
        _emit_requeue_event_audit(
            context=context,
            next_attempt=next_attempt,
            retry_at=next_retry_at.isoformat(),
            error_summary=error_summary,
        )
        return

    failure = await run_in_threadpool(
        mark_event_failed_sync,
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
        context_log.error(
            "full_sync_failure_transition_conflict",
            next_attempt=next_attempt,
            error_summary=error_summary,
        )
        return

    await handler.on_target_failed(
        context=context,
        next_attempt=next_attempt,
        error_summary=error_summary,
        retryable=retryable,
    )
    context_log.error(
        "full_sync_target_failed",
        next_attempt=next_attempt,
        retryable=retryable,
        error_summary=error_summary,
    )


async def _finalize_job_if_done(
    context: FullSyncContext,
    handler: IngestionHandlerProtocol,
) -> None:
    result = await run_in_threadpool(finalize_job_if_done_sync, context)
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
        _emit_job_audit(
            status=AuditStatus.SUCCESS,
            metadata=FullSyncJobAuditMetadata.from_job_result(
                context=context,
                total_targets=result.total_targets,
                completed_targets=result.completed_targets,
                failed_targets=result.failed_targets,
                requeued_targets=result.requeued_targets,
            ),
        )
        return

    await handler.on_job_failed(
        context=context,
        total_targets=result.total_targets,
        failed_targets=result.failed_targets,
    )
    _emit_job_audit(
        status=AuditStatus.FAILURE,
        level=AuditLevel.WARNING,
        metadata=FullSyncJobAuditMetadata.from_job_result(
            context=context,
            total_targets=result.total_targets,
            completed_targets=result.completed_targets,
            failed_targets=result.failed_targets,
            requeued_targets=result.requeued_targets,
        ),
    )


async def _deadletter_claim_failure(
    *,
    message: SyncStreamMessage,
    task_log: structlog.typing.FilteringBoundLogger,
    state: ClaimState,
) -> None:
    match state:
        case ClaimState.EVENT_NOT_FOUND:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_NOT_FOUND,
                error_message="sync event not found",
            )
            task_log.warning("full_sync_event_not_found")
        case ClaimState.JOB_NOT_FOUND:
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_NOT_FOUND,
                error_message="sync job not found",
            )
            task_log.warning("full_sync_job_not_found")
        case ClaimState.EVENT_JOB_MISMATCH:
            task_log.error("full_sync_event_job_mismatch")
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="event_id and job_id mismatch",
            )
        case ClaimState.EVENT_ALREADY_TERMINAL:
            task_log.warning("full_sync_event_already_terminal")
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_ALREADY_TERMINAL,
                error_message="event already terminal",
            )
        case ClaimState.EVENT_CAS_CONFLICT:
            task_log.warning("full_sync_event_claim_conflict")
            await deadletter(
                message=message,
                reason=SyncStreamFailureReason.EVENT_CAS_CONFLICT,
                error_message="event status transition CAS conflict",
            )
        case _:
            raise ValueError(f"unexpected full sync claim state: {state}")


def create_task_log(message: SyncStreamMessage):
    task = message.task
    return logger.bind(
        connector=task.connector,
        sync_type=task.sync_type.value,
        scope_id=task.scope_id,
        job_id=task.job_id,
        event_id=task.event_id,
        target_type=task.target_type,
        target_id=task.target_id,
        message_id=message.message_id,
    )


def create_context_log(context: FullSyncContext):
    return logger.bind(
        connector=context.connector,
        sync_type=context.sync_type.value,
        scope_id=context.scope_id,
        job_id=context.job_id,
        event_id=context.event_id,
        target_type=context.target_type,
        target_id=context.target_id,
    )


def _unsupported_handler_error(context: FullSyncContext) -> str:
    return (
        f"unsupported handler: connector={context.connector}, "
        f"sync_type={context.sync_type}"
    )


def _full_sync_retry_delay(exc: Exception, attempt: int) -> timedelta:
    return resolve_retry_delay(
        exc=exc,
        attempt=attempt,
        base_delay_seconds=settings.SYNC_JOB_RETRY_BASE_DELAY_SECONDS,
        max_delay_seconds=settings.SYNC_JOB_RETRY_MAX_DELAY_SECONDS,
    )


def _emit_job_audit(
    *,
    status: AuditStatus,
    metadata: FullSyncJobAuditMetadata,
    level: AuditLevel = AuditLevel.INFO,
) -> None:
    emit_audit_event(
        action=FullSyncAction.JOB,
        status=status,
        level=level,
        metadata=metadata,
    )


def _emit_requeue_event_audit(
    *,
    context: FullSyncContext,
    next_attempt: int,
    retry_at: str,
    error_summary: str,
) -> None:
    emit_audit_event(
        action=FullSyncAction.EVENT,
        status=AuditStatus.SUCCESS,
        level=AuditLevel.WARNING,
        metadata=FullSyncEventAuditMetadata.from_requeue(
            context=context,
            next_attempt=next_attempt,
            retry_at=retry_at,
            error_summary=error_summary,
        ),
    )
