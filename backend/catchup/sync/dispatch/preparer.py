from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEvent
from catchup.db.models import SyncType
from catchup.db.sync import find_active_full_sync_job
from catchup.db.sync import try_acquire_full_sync_scope_lock
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncEventSeed
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.common.schemas import SyncTrigger
from catchup.sync.event_publisher.event_record_persistence import (
    persist_sync_job_and_events,
)
from catchup.sync.event_publisher.stream_task_builder import (
    build_stream_tasks_from_persisted_events,
)
from catchup.sync.dispatch.observer import DispatchObserverContext
from catchup.sync.dispatch.observer import SyncDispatchObserver
from catchup.sync.dispatch.result_builder import DispatchResultBuilder


@dataclass(slots=True)
class PreparedDispatchState:
    context: DispatchObserverContext | None = None
    observer: SyncDispatchObserver | None = None
    db_event_ids: list[str] | None = None
    tasks: list[SyncStreamTask] | None = None
    conflict: SyncDispatchResult | None = None


class DispatchPreparer:
    def __init__(
        self,
        *,
        observer_resolver,
        result_builder: DispatchResultBuilder,
    ) -> None:
        self._observer_resolver = observer_resolver
        self._result_builder = result_builder

    def prepare(
        self,
        *,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        trigger: SyncTrigger,
        event_seeds: list[SyncEventSeed],
        base_url: str | None,
    ) -> PreparedDispatchState:
        normalized_scope_id = self._normalize_scope_id(scope_id)

        with SessionLocal() as db:
            conflict = self._check_dispatch_conflict(
                db=db,
                connector=connector,
                sync_type=sync_type,
                scope_id=normalized_scope_id,
                base_url=base_url,
            )
            if conflict is not None:
                db.rollback()
                return PreparedDispatchState(conflict=conflict)

            context = self._build_dispatch_context(
                connector=connector,
                sync_type=sync_type,
                scope_id=normalized_scope_id,
            )
            observer = self._resolve_observer(context)
            observer.on_dispatch_requested(
                context=context,
                trigger=trigger.value,
                event_seeds=event_seeds,
            )

            try:
                events = self._persist_events(
                    db=db,
                    context=context,
                    event_seeds=event_seeds,
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                observer.on_db_persist_failed(
                    context=context,
                    trigger=trigger.value,
                    event_seeds=event_seeds,
                    error=exc,
                )
                raise

            observer.on_db_persisted(
                context=context,
                trigger=trigger.value,
                event_seeds=event_seeds,
            )
            tasks = self._build_stream_tasks(
                context=context,
                events=events,
            )
            return PreparedDispatchState(
                context=context,
                observer=observer,
                db_event_ids=[event.event_id for event in events],
                tasks=tasks,
            )

    def _normalize_scope_id(self, scope_id: str) -> str:
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise SyncRequestError("scope_id is required")
        return normalized_scope_id

    def _build_dispatch_context(
        self,
        *,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
    ) -> DispatchObserverContext:
        return DispatchObserverContext(
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
            job_id=uuid4().hex,
            requested_at=datetime.now(timezone.utc),
        )

    def _check_dispatch_conflict(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        base_url: str | None,
    ) -> SyncDispatchResult | None:
        if sync_type != SyncType.FULL:
            return None

        if not try_acquire_full_sync_scope_lock(
            db,
            connector=connector,
            scope_id=scope_id,
        ):
            return SyncDispatchResult(
                status="conflict",
                connector=connector,
                scope_id=scope_id,
                message="another full sync dispatch is already being created for this scope",
            )

        active_job = find_active_full_sync_job(
            db,
            connector=connector,
            scope_id=scope_id,
        )
        if active_job is None:
            return None

        return self._result_builder.build_conflict_response(
            connector=connector,
            scope_id=scope_id,
            job_id=active_job.job_id,
            base_url=base_url,
        )

    def _persist_events(
        self,
        *,
        db: Session,
        context: DispatchObserverContext,
        event_seeds: Sequence[SyncEventSeed],
    ) -> list[SyncEvent]:
        events = persist_sync_job_and_events(
            db,
            job_id=context.job_id,
            connector=context.connector,
            sync_type=context.sync_type,
            scope_id=context.scope_id,
            requested_at=context.requested_at,
            event_seeds=list(event_seeds),
        )
        if len(events) != len(event_seeds):
            raise SyncInternalError(
                "persisted event count mismatch",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "requested_event_count": len(event_seeds),
                    "persisted_event_count": len(events),
                },
            )
        return events

    def _build_stream_tasks(
        self,
        *,
        context: DispatchObserverContext,
        events: Sequence[SyncEvent],
    ) -> list[SyncStreamTask]:
        tasks = build_stream_tasks_from_persisted_events(
            events=events,
            fallback_scope_id=context.scope_id,
        )
        if len(tasks) != len(events):
            raise SyncInternalError(
                "stream task build count mismatch",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "persisted_event_count": len(events),
                    "built_task_count": len(tasks),
                },
            )
        return tasks

    def _resolve_observer(
        self,
        context: DispatchObserverContext,
    ) -> SyncDispatchObserver:
        return self._observer_resolver(
            connector=context.connector,
            sync_type=context.sync_type,
        )
