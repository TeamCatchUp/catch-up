from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.incremental import list_debounce_ready_records
from catchup.db.incremental import list_retry_ready_records
from catchup.db.incremental import promote_record
from catchup.db.models import IncrementalRecordState
from catchup.db.models import SyncConnector

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
    return promote_record(db, record=record)
