from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncEventSeed
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.common.schemas import SyncTrigger

if TYPE_CHECKING:
    from catchup.sync.services.dispatch_observer import SyncDispatchObserver


@dataclass(slots=True, frozen=True)
class DispatchContext:
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    job_id: str
    requested_at: datetime

    @classmethod
    def create(
        cls,
        *,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
    ) -> "DispatchContext":
        return cls(
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
            job_id=uuid4().hex,
            requested_at=datetime.now(timezone.utc),
        )


@dataclass(slots=True, frozen=True)
class DispatchRequest:
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    trigger: SyncTrigger
    event_seeds: list[SyncEventSeed]
    base_url: str | None


@dataclass(slots=True, frozen=True)
class PrepareDispatchInput:
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    trigger: SyncTrigger
    event_seeds: list[SyncEventSeed]
    base_url: str | None

    @classmethod
    def from_request(cls, request: DispatchRequest) -> "PrepareDispatchInput":
        return cls(
            connector=request.connector,
            sync_type=request.sync_type,
            scope_id=request.scope_id,
            trigger=request.trigger,
            event_seeds=request.event_seeds,
            base_url=request.base_url,
        )


@dataclass(slots=True, frozen=True)
class PublishDispatchInput:
    context: DispatchContext
    tasks: list[SyncStreamTask]
    trigger: SyncTrigger
    target_count: int
    observer: SyncDispatchObserver

    @classmethod
    def from_request(
        cls,
        request: DispatchRequest,
        *,
        context: DispatchContext,
        tasks: list[SyncStreamTask],
        observer: SyncDispatchObserver,
    ) -> "PublishDispatchInput":
        return cls(
            context=context,
            tasks=tasks,
            trigger=request.trigger,
            target_count=len(request.event_seeds),
            observer=observer,
        )


@dataclass(slots=True)
class PreparedDispatchState:
    context: DispatchContext | None = None
    observer: SyncDispatchObserver | None = None
    db_event_ids: list[str] | None = None
    tasks: list[SyncStreamTask] | None = None
    conflict: SyncDispatchResult | None = None

    @classmethod
    def conflict_result(cls, conflict: SyncDispatchResult) -> "PreparedDispatchState":
        return cls(conflict=conflict)

    @classmethod
    def ready(
        cls,
        *,
        context: DispatchContext,
        observer: SyncDispatchObserver,
        db_event_ids: list[str],
        tasks: list[SyncStreamTask],
    ) -> "PreparedDispatchState":
        return cls(
            context=context,
            observer=observer,
            db_event_ids=db_event_ids,
            tasks=tasks,
        )
