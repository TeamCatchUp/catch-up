from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import (
    IncrementalOutboxCreateInput,
    create_outbox_entry,
    list_debounce_ready_records,
    list_retry_ready_records,
    update_record_status_cas,
)
from catchup.db.models import IncrementalRecordState, IncrementalRecordStatus, SyncConnector

logger = logging.getLogger(__name__)


def promote_incremental_records(
    *,
    connector: SyncConnector | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    batch_limit = max(1, limit or int(settings.INCREMENTAL_PROMOTER_BATCH_SIZE))

    with SessionLocal() as db:
        debounce_ready = list_debounce_ready_records(
            db,
            connector=connector,
            limit=batch_limit,
        )
        retry_ready = list_retry_ready_records(
            db,
            connector=connector,
            limit=batch_limit,
        )

        promoted = 0
        skipped = 0
        errors = 0

        for record in [*debounce_ready, *retry_ready]:
            try:
                if _promote_record(db, record):
                    promoted += 1
                else:
                    skipped += 1
            except Exception:
                logger.exception(
                    "[INCREMENTAL][PROMOTER] Failed to promote record: record_key=%s, generation=%s",
                    record.record_key,
                    record.generation,
                )
                errors += 1

    return {
        "promoted": promoted,
        "skipped": skipped,
        "errors": errors,
    }


def _promote_record(db: Session, record: IncrementalRecordState) -> bool:
    from_status = (
        IncrementalRecordStatus.RETRY_WAIT
        if record.status == IncrementalRecordStatus.RETRY_WAIT
        else IncrementalRecordStatus.DEBOUNCING
    )
    if not update_record_status_cas(
        db,
        record_key=record.record_key,
        from_statuses=[from_status],
        to_status=IncrementalRecordStatus.QUEUED,
        expected_generation=record.generation,
        queued_generation=record.generation,
    ):
        return False

    create_outbox_entry(
        db,
        IncrementalOutboxCreateInput(
            record_key=record.record_key,
            generation=record.generation,
            connector=record.connector,
            scope_id=record.scope_id,
            parent_type=record.parent_type,
            parent_id=record.parent_id,
            event_kind=record.event_kind,
        ),
    )
    return True
