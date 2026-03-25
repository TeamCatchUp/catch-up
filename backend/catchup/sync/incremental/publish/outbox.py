from __future__ import annotations

from dataclasses import dataclass
import logging

from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import (
    claim_outbox_for_publish,
    complete_outbox_publish,
    complete_outbox_skip,
    fail_outbox_publish,
    get_record_state,
    list_pending_outbox_entries,
    recover_stale_outbox_claims,
    transition_record_status,
)
from catchup.db.models import (
    IncrementalOutboxStatus,
    IncrementalRecordStatus,
    IncrementalStreamOutbox,
    SyncConnector,
)
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.incremental.policy.full_sync_guard import is_incremental_target_eligible
from catchup.sync.stream_runtime.stream_queue import publish_task

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class IncrementalPublishBatch:
    recovered: int
    outbox_entries: list[IncrementalStreamOutbox]


@dataclass(slots=True, frozen=True)
class IncrementalPublishPreparation:
    task: SyncStreamTask | None = None
    blocked: bool = False
    skipped: bool = False
    log_message: str | None = None


def _connector_key(connector: SyncConnector | str) -> str:
    if isinstance(connector, SyncConnector):
        return connector.value
    return str(connector).strip()


def build_incremental_event_id(record_key: str, generation: int) -> str:
    return f"inc:{record_key}:{generation}"


def build_incremental_job_id(
    *,
    connector: str,
    scope_id: str,
    parent_type: str,
    parent_id: str,
) -> str:
    return f"inc:{connector}:{scope_id}:{parent_type}:{parent_id}"


def _load_publish_batch_sync(
    *,
    connector: SyncConnector | None,
    batch_limit: int,
) -> IncrementalPublishBatch:
    with SessionLocal() as db:
        recovered = recover_stale_outbox_claims(
            db,
            stale_seconds=max(1, int(settings.INCREMENTAL_OUTBOX_PUBLISHING_STALE_SECONDS)),
            connector=connector,
            limit=batch_limit,
        )
        outbox_entries = list_pending_outbox_entries(
            db,
            connector=connector,
            statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
            limit=batch_limit,
        )
    return IncrementalPublishBatch(
        recovered=recovered,
        outbox_entries=outbox_entries,
    )


def _prepare_publish_sync(
    *,
    outbox_id: int,
    record_key: str,
    generation: int,
    attempt: int,
) -> IncrementalPublishPreparation:
    with SessionLocal() as db:
        if not claim_outbox_for_publish(db, outbox_id=outbox_id):
            return IncrementalPublishPreparation(skipped=True)

        record = get_record_state(db, record_key)
        if record is None:
            return IncrementalPublishPreparation(
                skipped=complete_outbox_skip(
                    db,
                    outbox_id=outbox_id,
                    last_error="record_not_found",
                )
            )

        if (
            record.generation != generation
            or record.status != IncrementalRecordStatus.QUEUED
        ):
            return IncrementalPublishPreparation(
                skipped=complete_outbox_skip(
                    db,
                    outbox_id=outbox_id,
                    last_error="stale_outbox",
                )
            )

        connector_key = _connector_key(record.connector)
        if not is_incremental_target_eligible(
            db,
            connector=connector_key,
            scope_id=record.scope_id,
            target_type=record.parent_type,
            target_id=record.parent_id,
        ):
            transition_record_status(
                db,
                record_key=record.record_key,
                from_statuses=[IncrementalRecordStatus.QUEUED],
                to_status=IncrementalRecordStatus.DEAD,
                expected_generation=record.generation,
                attempt=int(record.attempt),
                last_error="full_sync_required",
            )
            blocked = complete_outbox_skip(
                db,
                outbox_id=outbox_id,
                last_error="full_sync_required",
            )
            if not blocked:
                return IncrementalPublishPreparation(skipped=True)

            return IncrementalPublishPreparation(
                blocked=True,
                log_message=(
                    "[INCREMENTAL][PUBLISH] Skipped due to missing full sync: "
                    f"connector={connector_key}, scope_id={record.scope_id}, "
                    f"parent_type={record.parent_type}, parent_id={record.parent_id}, "
                    f"record_key={record.record_key}, generation={record.generation}"
                ),
            )

        task = SyncStreamTask.incremental(
            event_id=build_incremental_event_id(record.record_key, record.generation),
            job_id=build_incremental_job_id(
                connector=connector_key,
                scope_id=record.scope_id,
                parent_type=record.parent_type,
                parent_id=record.parent_id,
            ),
            connector=connector_key,
            scope_id=record.scope_id,
            target_type=record.parent_type,
            target_id=record.parent_id,
            record_key=record.record_key,
            generation=record.generation,
            record_type=record.record_type,
            record_id=record.record_id,
            parent_type=record.parent_type,
            parent_id=record.parent_id,
            event_kind=record.event_kind,
            last_event_at=record.last_event_at.isoformat(),
            attempt=max(1, attempt),
            max_attempts=max(1, int(settings.INCREMENTAL_MAX_ATTEMPTS)),
        )
        return IncrementalPublishPreparation(task=task)


def _complete_publish_success_sync(
    *,
    outbox_id: int,
    message_id: str,
) -> bool:
    with SessionLocal() as db:
        return complete_outbox_publish(
            db,
            outbox_id=outbox_id,
            stream_message_id=message_id,
            last_error=None,
        )


def _fail_publish_sync(
    *,
    outbox_id: int,
    error_message: str,
) -> None:
    with SessionLocal() as db:
        fail_outbox_publish(
            db,
            outbox_id=outbox_id,
            last_error=error_message,
        )


async def publish_incremental_outbox(
    *,
    connector: SyncConnector | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    batch_limit = max(1, limit or int(settings.INCREMENTAL_OUTBOX_BATCH_SIZE))
    batch = await run_in_threadpool(
        _load_publish_batch_sync,
        connector=connector,
        batch_limit=batch_limit,
    )

    published = 0
    blocked = 0
    skipped = 0
    errors = 0

    for entry in batch.outbox_entries:
        try:
            preparation = await run_in_threadpool(
                _prepare_publish_sync,
                outbox_id=entry.id,
                record_key=entry.record_key,
                generation=entry.generation,
                attempt=int(entry.attempt),
            )
            if preparation.skipped:
                skipped += 1
                continue
            if preparation.blocked:
                blocked += 1
                if preparation.log_message:
                    logger.info(preparation.log_message)
                continue
            if preparation.task is None:
                skipped += 1
                continue

            message_id = await publish_task(preparation.task)

            if await run_in_threadpool(
                _complete_publish_success_sync,
                outbox_id=entry.id,
                message_id=message_id,
            ):
                published += 1
                continue

            skipped += 1
        except Exception as exc:
            logger.exception(
                "[INCREMENTAL][PUBLISH] Failed to publish outbox: outbox_id=%s, record_key=%s, generation=%s",
                entry.id,
                entry.record_key,
                entry.generation,
            )
            await run_in_threadpool(
                _fail_publish_sync,
                outbox_id=entry.id,
                error_message=str(exc),
            )
            errors += 1

    return {
        "published": published,
        "blocked_full_sync_required": blocked,
        "skipped": skipped,
        "errors": errors,
        "recovered": batch.recovered,
    }
