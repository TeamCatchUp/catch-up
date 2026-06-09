from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import TypeAlias

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.enums import SyncEventKind
from catchup.sync.common.enums import SyncTargetType


@dataclass(slots=True)
class SyncContextBase:
    event_id: str
    job_id: str
    connector: SyncConnector
    scope_id: str
    target_type: SyncTargetType
    target_id: str
    target_name: str
    attempt: int
    max_attempts: int

    def __post_init__(self) -> None:
        self.connector = SyncConnector(self.connector)
        self.target_type = SyncTargetType(self.target_type)


@dataclass(slots=True)
class FullSyncContext(SyncContextBase):
    sync_from_ts: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    sync_type: SyncType = field(init=False, default=SyncType.FULL)


@dataclass(slots=True)
class IncrementalSyncContext(SyncContextBase):
    record_key: str
    generation: int
    record_type: str | None = None
    record_id: str | None = None
    parent_type: SyncTargetType = SyncTargetType.RESOURCE
    parent_id: str = ""
    event_kind: SyncEventKind = SyncEventKind.UPDATED
    last_event_at: str = ""
    sync_type: SyncType = field(init=False, default=SyncType.INCREMENTAL)

    def __post_init__(self) -> None:
        SyncContextBase.__post_init__(self)
        self.parent_type = SyncTargetType(self.parent_type)
        self.event_kind = SyncEventKind(self.event_kind)


SyncContext: TypeAlias = FullSyncContext | IncrementalSyncContext


@dataclass(slots=True, frozen=True)
class PageIngestionRequest:
    context: SyncContext
    page: object
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RecordIngestionRequest:
    context: SyncContext
    record: object
    metadata: dict[str, object] = field(default_factory=dict)
