from __future__ import annotations

import logging

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import (
    get_record_state,
    list_pending_outbox_entries,
    update_outbox_status_cas,
)
from catchup.db.models import IncrementalOutboxStatus, IncrementalRecordStatus, SyncConnector
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.stream_runtime.stream_queue import publish_task

logger = logging.getLogger(__name__)


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


async def publish_incremental_outbox(
    *,
    connector: SyncConnector | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    batch_limit = max(1, limit or int(settings.INCREMENTAL_OUTBOX_BATCH_SIZE))

    with SessionLocal() as db:
        outbox_entries = list_pending_outbox_entries(
            db,
            connector=connector,
            statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
            limit=batch_limit,
        )

    published = 0
    skipped = 0
    errors = 0

    for entry in outbox_entries:
        try:
            with SessionLocal() as db:
                record = get_record_state(db, entry.record_key)
                if record is None:
                    skipped += 1
                    continue

                if record.generation != entry.generation or record.status != IncrementalRecordStatus.QUEUED:
                    if update_outbox_status_cas(
                        db,
                        outbox_id=entry.id,
                        from_statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
                        to_status=IncrementalOutboxStatus.PUBLISHED,
                        stream_message_id="stale-skipped",
                        last_error="stale_outbox",
                    ):
                        skipped += 1
                    continue

                task = SyncStreamTask(
                    event_id=build_incremental_event_id(record.record_key, record.generation),
                    job_id=build_incremental_job_id(
                        connector=record.connector.value,
                        scope_id=record.scope_id,
                        parent_type=record.parent_type,
                        parent_id=record.parent_id,
                    ),
                    connector=record.connector.value,
                    sync_type="incremental",
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
                    attempt=record.attempt,
                    max_attempts=max(1, int(settings.INCREMENTAL_MAX_ATTEMPTS)),
                )

            message_id = await publish_task(task)

            with SessionLocal() as db:
                if update_outbox_status_cas(
                    db,
                    outbox_id=entry.id,
                    from_statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
                    to_status=IncrementalOutboxStatus.PUBLISHED,
                    stream_message_id=message_id,
                    last_error=None,
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
            with SessionLocal() as db:
                update_outbox_status_cas(
                    db,
                    outbox_id=entry.id,
                    from_statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
                    to_status=IncrementalOutboxStatus.FAILED,
                    last_error=str(exc),
                    increment_attempt=True,
                )
            errors += 1

    return {
        "published": published,
        "skipped": skipped,
        "errors": errors,
    }
