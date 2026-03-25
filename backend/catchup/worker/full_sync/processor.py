from __future__ import annotations

from datetime import datetime
from datetime import timezone

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJobStatus
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.protocols import FullSyncCollectingHandlerProtocol
from catchup.sync.common.protocols import FullSyncValidatingHandlerProtocol
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.retry_policy import is_retryable_sync_error
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.worker.common import build_job_status_event
from catchup.worker.common import build_target_status_event
from catchup.worker.common import deadletter
from catchup.worker.common import publish_status_event
from catchup.worker.common import select_handler
from catchup.worker.full_sync.claim import _claim_event
from catchup.worker.full_sync.job_finalizer import _finalize_job_if_done
from catchup.worker.full_sync.state_store import _full_sync_retry_delay
from catchup.worker.full_sync.state_store import _mark_event_failed_sync
from catchup.worker.full_sync.state_store import _persist_event_metadata
from catchup.worker.full_sync.state_store import _schedule_event_retry_sync
from catchup.worker.full_sync.validation_flow import _complete_event_success
from catchup.worker.full_sync.validation_flow import _run_full_sync_validation_flow

logger = structlog.get_logger()


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
        if context is not None and handler is not None:
            await _finalize_job_if_done(context, handler)
