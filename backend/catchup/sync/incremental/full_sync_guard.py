from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector
from catchup.db.sync import has_active_full_sync_event
from catchup.db.sync import has_successful_full_sync_event
from catchup.sync.incremental.schemas import RecordChange

_CHANNEL_TALK_USER_CHAT_RECORD_TYPE = "user_chat"
_CHANNEL_TALK_CHANNEL_TARGET_TYPE = "channel"


@dataclass(slots=True, frozen=True)
class IncrementalTarget:
    connector: str
    scope_id: str
    target_type: str
    target_id: str

    @property
    def cache_key(self) -> tuple[str, str, str, str]:
        return (
            self.connector,
            self.scope_id,
            self.target_type,
            self.target_id,
        )


@dataclass(slots=True, frozen=True)
class RecordChangeGuardResult:
    allowed_changes: list[RecordChange]
    waiting_changes: list[RecordChange]
    blocked_changes: list[RecordChange]

    @property
    def blocked_targets(self) -> list[IncrementalTarget]:
        unique_targets: dict[tuple[str, str, str, str], IncrementalTarget] = {}
        for change in self.blocked_changes:
            target = build_incremental_target(change)
            unique_targets.setdefault(target.cache_key, target)
        return list(unique_targets.values())


def build_incremental_target(change: RecordChange) -> IncrementalTarget:
    return IncrementalTarget(
        connector=change.connector.value,
        scope_id=change.scope_id.strip(),
        target_type=change.parent_type.strip(),
        target_id=change.parent_id.strip(),
    )


def is_incremental_target_eligible(
    db: Session,
    *,
    connector: str,
    scope_id: str,
    target_type: str,
    target_id: str,
) -> bool:
    normalized_scope_id = scope_id.strip()
    normalized_target_type = target_type.strip()
    normalized_target_id = target_id.strip()
    if not normalized_scope_id or not normalized_target_type or not normalized_target_id:
        return False

    return has_successful_full_sync_event(
        db,
        connector=SyncConnector(connector),
        scope_id=normalized_scope_id,
        resource_type=normalized_target_type,
        resource_id=normalized_target_id,
    )


def is_incremental_target_waiting_on_full_sync(
    db: Session,
    *,
    change: RecordChange,
) -> bool:
    if change.connector != SyncConnector.CHANNEL_TALK:
        return False
    if change.record_type.strip() != _CHANNEL_TALK_USER_CHAT_RECORD_TYPE:
        return False
    if change.parent_type.strip() != _CHANNEL_TALK_CHANNEL_TARGET_TYPE:
        return False

    normalized_scope_id = change.scope_id.strip()
    normalized_parent_id = change.parent_id.strip()
    if not normalized_scope_id or normalized_parent_id != normalized_scope_id:
        return False

    return has_active_full_sync_event(
        db,
        connector=change.connector,
        scope_id=normalized_scope_id,
        resource_type=_CHANNEL_TALK_CHANNEL_TARGET_TYPE,
        resource_id=normalized_scope_id,
    )


def filter_record_changes_by_full_sync(
    db: Session,
    changes: list[RecordChange],
) -> RecordChangeGuardResult:
    allowed_changes: list[RecordChange] = []
    waiting_changes: list[RecordChange] = []
    blocked_changes: list[RecordChange] = []
    eligibility_cache: dict[tuple[str, str, str, str], bool] = {}
    waiting_cache: dict[tuple[str, str, str, str, str], bool] = {}

    for change in changes:
        target = build_incremental_target(change)
        cache_key = target.cache_key
        waiting_cache_key = (*cache_key, change.record_type.strip())
        waiting = waiting_cache.get(waiting_cache_key)
        if waiting is None:
            waiting = is_incremental_target_waiting_on_full_sync(db, change=change)
            waiting_cache[waiting_cache_key] = waiting

        if waiting:
            waiting_changes.append(change)
            continue

        eligible = eligibility_cache.get(cache_key)
        if eligible is None:
            eligible = is_incremental_target_eligible(
                db,
                connector=target.connector,
                scope_id=target.scope_id,
                target_type=target.target_type,
                target_id=target.target_id,
            )
            eligibility_cache[cache_key] = eligible

        if eligible:
            allowed_changes.append(change)
        else:
            blocked_changes.append(change)

    return RecordChangeGuardResult(
        allowed_changes=allowed_changes,
        waiting_changes=waiting_changes,
        blocked_changes=blocked_changes,
    )
