from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.sync import SyncEventPublishResultInput
from catchup.db.sync import claim_events_for_republish
from catchup.db.sync import get_event
from catchup.db.sync import get_job
from catchup.db.sync import list_retry_ready_events
from catchup.db.sync import mark_event_retrying
from catchup.db.sync import record_event_publish_outcomes
from catchup.db.sync import requeue_retrying_event
from catchup.sync.common.retry_policy import calculate_retry_delay
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.event_publisher.stream_task_builder import (
    build_stream_task_from_persisted_event,
)
from catchup.sync.stream_runtime.stream_queue import publish_task

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class FullSyncRetryPublishItem:
    event_id: str
    task: SyncStreamTask | None = None
    skipped: bool = False
    error_message: str | None = None


def _load_retry_ready_event_ids_sync(*, limit: int) -> list[str]:
    with SessionLocal() as db:
        events = list_retry_ready_events(
            db,
            now=datetime.now(timezone.utc),
            limit=limit,
        )
        return [event.event_id for event in events]


def _prepare_retry_publish_sync(event_id: str) -> FullSyncRetryPublishItem:
    with SessionLocal() as db:
        try:
            event = get_event(db, event_id)
            if event is None:
                db.rollback()
                return FullSyncRetryPublishItem(
                    event_id=event_id,
                    skipped=True,
                    error_message="event_not_found",
                )

            if not requeue_retrying_event(
                db,
                event_id,
                ready_at=datetime.now(timezone.utc),
                require_due=True,
            ):
                db.rollback()
                return FullSyncRetryPublishItem(
                    event_id=event_id,
                    skipped=True,
                    error_message="retry_not_ready",
                )

            if not claim_events_for_republish(db, event_ids=[event_id]):
                db.rollback()
                return FullSyncRetryPublishItem(
                    event_id=event_id,
                    skipped=True,
                    error_message="publish_state_conflict",
                )

            claimed = get_event(db, event_id)
            if claimed is None:
                db.rollback()
                return FullSyncRetryPublishItem(
                    event_id=event_id,
                    skipped=True,
                    error_message="event_not_found",
                )

            job = get_job(db, claimed.job_id)
            if job is None:
                db.rollback()
                return FullSyncRetryPublishItem(
                    event_id=event_id,
                    skipped=True,
                    error_message="job_not_found",
                )

            task = build_stream_task_from_persisted_event(
                event=claimed,
                fallback_scope_id=job.scope_id,
            )

            db.commit()
            return FullSyncRetryPublishItem(
                event_id=event_id,
                task=task,
            )
        except Exception:
            db.rollback()
            raise


def _record_retry_publish_outcome_sync(
    *,
    event_id: str,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    if message_id is None and error_message is None:
        raise ValueError("retry publish outcome requires message_id or error_message")

    published = (
        [
            SyncEventPublishResultInput(
                event_id=event_id,
                stream_message_id=message_id,
            )
        ]
        if message_id is not None
        else []
    )
    failed_event_ids = [event_id] if error_message is not None else []

    with SessionLocal() as db:
        try:
            if not record_event_publish_outcomes(
                db,
                published=published,
                failed_event_ids=failed_event_ids,
                publish_error=error_message,
            ):
                db.rollback()
                raise RuntimeError("failed to persist retry publish outcome")

            db.commit()
        except Exception:
            db.rollback()
            raise


def _reschedule_retry_publish_failure_sync(
    *,
    event_id: str,
    error_message: str,
) -> None:
    with SessionLocal() as db:
        try:
            event = get_event(db, event_id)
            if event is None:
                db.rollback()
                raise RuntimeError(f"event not found for retry publish failure: {event_id}")

            if not record_event_publish_outcomes(
                db,
                published=[],
                failed_event_ids=[event_id],
                publish_error=error_message,
            ):
                db.rollback()
                raise RuntimeError("failed to persist retry publish failure")

            retry_delay = calculate_retry_delay(
                attempt=max(1, int(event.attempt)),
                base_delay_seconds=settings.SYNC_JOB_RETRY_BASE_DELAY_SECONDS,
                max_delay_seconds=settings.SYNC_JOB_RETRY_MAX_DELAY_SECONDS,
            )
            next_retry_at = datetime.now(timezone.utc) + retry_delay

            if not mark_event_retrying(
                db,
                event_id,
                from_statuses=[SyncEventStatus.PENDING],
                next_retry_at=next_retry_at,
                last_error=error_message,
            ):
                db.rollback()
                raise RuntimeError("failed to reschedule retry publish failure")

            db.commit()
        except Exception:
            db.rollback()
            raise


async def publish_retry_ready_full_sync_events(
    *,
    limit: int,
) -> dict[str, int]:
    event_ids = await run_in_threadpool(
        _load_retry_ready_event_ids_sync,
        limit=limit,
    )

    published = 0
    skipped = 0
    errors = 0

    for event_id in event_ids:
        try:
            item = await run_in_threadpool(_prepare_retry_publish_sync, event_id)
            if item.skipped or item.task is None:
                skipped += 1
                continue

            message_id = await publish_task(item.task)
            await run_in_threadpool(
                _record_retry_publish_outcome_sync,
                event_id=event_id,
                message_id=message_id,
            )
            published += 1
        except Exception as exc:
            errors += 1
            logger.exception(
                "[FULL][RETRY] Failed to publish retry-ready event: event_id=%s",
                event_id,
            )
            try:
                await run_in_threadpool(
                    _reschedule_retry_publish_failure_sync,
                    event_id=event_id,
                    error_message=str(exc),
                )
            except Exception:
                logger.exception(
                    "[FULL][RETRY] Failed to persist retry publish failure: event_id=%s",
                    event_id,
                )

    return {
        "published": published,
        "skipped": skipped,
        "errors": errors,
    }
