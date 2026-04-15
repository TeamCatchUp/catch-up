from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from catchup.configs.config import settings
from catchup.db.incremental import IncrementalRecordChangeInput
from catchup.db.models import SyncConnector


@dataclass(slots=True, frozen=True)
class RecordChange:
    connector: SyncConnector
    scope_id: str
    record_type: str
    record_id: str
    parent_type: str
    parent_id: str
    event_kind: str
    last_event_at: datetime

    @property
    def record_key(self) -> str:
        return build_record_key(
            connector=self.connector,
            scope_id=self.scope_id,
            parent_type=self.parent_type,
            parent_id=self.parent_id,
            record_type=self.record_type,
            record_id=self.record_id,
        )

    def to_input(self) -> IncrementalRecordChangeInput:
        return IncrementalRecordChangeInput(
            record_key=self.record_key,
            connector=self.connector,
            scope_id=self.scope_id,
            record_type=self.record_type,
            record_id=self.record_id,
            parent_type=self.parent_type,
            parent_id=self.parent_id,
            event_kind=self.event_kind,
            last_event_at=to_utc(self.last_event_at),
            debounce_until=build_debounce_until(self.last_event_at),
        )


@dataclass(slots=True, frozen=True)
class IncrementalIngestResult:
    record_keys: list[str]
    blocked_count: int
    blocked_target_keys: list[str]
    first_allowed_change: RecordChange | None = None


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_debounce_until(last_event_at: datetime) -> datetime:
    return to_utc(last_event_at) + timedelta(
        seconds=max(1, int(settings.INCREMENTAL_DEBOUNCE_SECONDS))
    )


def build_record_key(
    *,
    connector: SyncConnector,
    scope_id: str,
    parent_type: str,
    parent_id: str,
    record_type: str,
    record_id: str,
) -> str:
    return ":".join(
        [
            connector.value,
            scope_id.strip(),
            parent_type.strip(),
            parent_id.strip(),
            record_type.strip(),
            record_id.strip(),
        ]
    )
