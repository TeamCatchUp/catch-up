from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from catchup.db.sync import has_successful_full_sync_event
from catchup.sync.incremental.ingest.schemas import RecordChange


@dataclass(slots=True, frozen=True)
class IncrementalTarget:
    connector: str
    scope_id: str
    target_type: str
    target_id: str


@dataclass(slots=True, frozen=True)
class RecordChangeGuardResult:
    allowed_changes: list[RecordChange]
    blocked_changes: list[RecordChange]

    @property
    def blocked_targets(self) -> list[IncrementalTarget]:
        unique_targets: dict[tuple[str, str, str, str], IncrementalTarget] = {}
        for change in self.blocked_changes:
            target = build_incremental_target(change)
            unique_targets.setdefault(
                (
                    target.connector,
                    target.scope_id,
                    target.target_type,
                    target.target_id,
                ),
                target,
            )
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

    from catchup.db.models import SyncConnector

    return has_successful_full_sync_event(
        db,
        connector=SyncConnector(connector),
        scope_id=normalized_scope_id,
        resource_type=normalized_target_type,
        resource_id=normalized_target_id,
    )


def filter_record_changes_by_full_sync(
    db: Session,
    changes: list[RecordChange],
) -> RecordChangeGuardResult:
    allowed_changes: list[RecordChange] = []
    blocked_changes: list[RecordChange] = []
    eligibility_cache: dict[tuple[str, str, str, str], bool] = {}

    for change in changes:
        target = build_incremental_target(change)
        cache_key = (
            target.connector,
            target.scope_id,
            target.target_type,
            target.target_id,
        )
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
        blocked_changes=blocked_changes,
    )
