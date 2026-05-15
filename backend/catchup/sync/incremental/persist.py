from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.incremental import upsert_record_change
from catchup.db.incremental import upsert_waiting_full_sync_record_change
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
        persisted = _persist_record_changes(
            db,
            allowed_changes=guard_result.allowed_changes,
            waiting_changes=guard_result.waiting_changes,
        )
        first_allowed_change = _first_accepted_change(
            allowed_changes=guard_result.allowed_changes,
            waiting_changes=persisted.accepted_waiting_changes,
        )
        return IncrementalIngestResult(
            record_keys=persisted.record_keys,
            blocked_count=len(guard_result.blocked_changes),
            blocked_target_keys=blocked_targets,
            first_allowed_change=first_allowed_change,
        )


@dataclass(slots=True)
class PersistedRecordChanges:
    record_keys: list[str]
    accepted_waiting_changes: list[RecordChange]


def _first_accepted_change(
    *,
    allowed_changes: list[RecordChange],
    waiting_changes: list[RecordChange],
) -> RecordChange | None:
    if allowed_changes:
        return allowed_changes[0]
    if waiting_changes:
        return waiting_changes[0]
    return None


def _persist_record_changes(
    db: Session,
    *,
    allowed_changes: list[RecordChange],
    waiting_changes: list[RecordChange],
) -> PersistedRecordChanges:
    record_keys: list[str] = []
    accepted_waiting_changes: list[RecordChange] = []

    for change in allowed_changes:
        state = upsert_record_change(db, change.to_input())
        record_keys.append(state.record_key)

    for change in waiting_changes:
        state = upsert_waiting_full_sync_record_change(db, change.to_input())
        if state is not None:
            record_keys.append(state.record_key)
            accepted_waiting_changes.append(change)

    db.commit()
    return PersistedRecordChanges(
        record_keys=record_keys,
        accepted_waiting_changes=accepted_waiting_changes,
    )
