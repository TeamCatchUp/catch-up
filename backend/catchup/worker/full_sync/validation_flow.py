from __future__ import annotations

from datetime import datetime
from datetime import timezone

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.db.models import SyncEventStatus
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.protocols import FullSyncValidatingHandlerProtocol
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import FullSyncRepairStatus
from catchup.sync.common.schemas import FullSyncValidationResult
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.worker.common import build_target_status_event
from catchup.worker.common import deadletter
from catchup.worker.common import publish_status_event
from catchup.worker.full_sync.state_store import _clear_event_missing_records_sync
from catchup.worker.full_sync.state_store import _mark_event_success_sync
from catchup.worker.full_sync.state_store import _persist_event_metadata
from catchup.worker.full_sync.state_store import _persist_sync_result
from catchup.worker.full_sync.state_store import _persist_validation_result
from catchup.worker.full_sync.state_store import _store_event_missing_records_sync

logger = structlog.get_logger()


def _has_retry_attempt_remaining(context: FullSyncContext) -> bool:
    return (context.attempt + 1) < context.max_attempts


def _missing_ratio(validation_result: FullSyncValidationResult) -> float:
    if validation_result.expected_count <= 0:
        return 0.0
    return validation_result.missing_count / validation_result.expected_count


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
            "execution_phase": "validating" if should_retry else "completed",
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
            "execution_phase": "repairing" if should_retry else "completed",
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
