from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.sync import SyncEventMissingRecordInput
from catchup.db.sync import clear_event_missing_records
from catchup.db.sync import mark_event_failed
from catchup.db.sync import mark_event_retrying
from catchup.db.sync import mark_event_success
from catchup.db.sync import replace_event_missing_records
from catchup.db.sync import update_event_resource_metadata
from catchup.sync.common.canonical_ids import split_canonical_id
from catchup.sync.common.retry_policy import resolve_retry_delay
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import FullSyncRepairStatus
from catchup.sync.common.schemas import FullSyncValidationResult
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.schemas import FailureResult


def _full_sync_retry_delay(exc: Exception, attempt: int) -> timedelta:
    return resolve_retry_delay(
        exc=exc,
        attempt=attempt,
        base_delay_seconds=settings.SYNC_JOB_RETRY_BASE_DELAY_SECONDS,
        max_delay_seconds=settings.SYNC_JOB_RETRY_MAX_DELAY_SECONDS,
    )


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
