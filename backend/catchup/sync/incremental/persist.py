from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.incremental import upsert_record_change
from catchup.sync.incremental.full_sync_guard import filter_record_changes_by_full_sync
from catchup.sync.incremental.schemas import IncrementalIngestResult
from catchup.sync.incremental.schemas import RecordChange


def persist_incremental_changes(changes: list[RecordChange]) -> IncrementalIngestResult:
    if not changes:
        return IncrementalIngestResult(
            record_keys=[],
            blocked_count=0,
            blocked_target_keys=[],
        )

    with SessionLocal() as db:
        guard_result = filter_record_changes_by_full_sync(db, changes)
        blocked_targets = [
            f"{target.target_type}:{target.target_id}"
            for target in guard_result.blocked_targets
        ]
        record_keys = _persist_record_changes(db, guard_result.allowed_changes)
        first_allowed_change = (
            guard_result.allowed_changes[0]
            if guard_result.allowed_changes
            else None
        )
        return IncrementalIngestResult(
            record_keys=record_keys,
            blocked_count=len(guard_result.blocked_changes),
            blocked_target_keys=blocked_targets,
            first_allowed_change=first_allowed_change,
        )


def _persist_record_changes(
    db: Session,
    changes: list[RecordChange],
) -> list[str]:
    if not changes:
        return []

    record_keys: list[str] = []
    for change in changes:
        state = upsert_record_change(db, change.to_input())
        record_keys.append(state.record_key)

    db.commit()
    return record_keys
