from __future__ import annotations

from typing import Sequence

import structlog
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEvent
from catchup.db.models import SyncType
from catchup.db.sync import find_active_full_sync_job
from catchup.db.sync import try_acquire_full_sync_scope_lock
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.event_publisher.event_record_persistence import (
    persist_sync_job_and_events,
)
from catchup.sync.event_publisher.stream_task_builder import (
    build_stream_tasks_from_persisted_events,
)
from catchup.sync.dispatch.result_builder import build_conflict_response
from catchup.sync.dispatch.types import DispatchContext
from catchup.sync.dispatch.types import PreparedDispatchState
from catchup.sync.dispatch.types import PrepareDispatchInput
from catchup.sync.services.dispatch_observer import resolve_sync_dispatch_observer

logger = structlog.get_logger(__name__)


class DispatchPreparer:
    def prepare(self, data: PrepareDispatchInput) -> PreparedDispatchState:
        with SessionLocal() as db:
            conflict = self._check_dispatch_conflict(
                db=db,
                data=data,
            )
            if conflict is not None:
                db.rollback()
                return PreparedDispatchState.conflict_result(conflict)

            context = DispatchContext.create(
                connector=data.connector,
                sync_type=data.sync_type,
                scope_id=data.scope_id,
            )
            observer = resolve_sync_dispatch_observer(
                connector=context.connector,
                sync_type=context.sync_type,
            )
            observer.on_dispatch_requested(
                context=context,
                trigger=data.trigger.value,
                event_seeds=data.event_seeds,
            )

            try:
                events = self._persist_events(
                    db=db,
                    context=context,
                    event_seeds=data.event_seeds,
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                observer.on_db_persist_failed(
                    context=context,
                    trigger=data.trigger.value,
                    event_seeds=data.event_seeds,
                    error=exc,
                )
                raise

            observer.on_db_persisted(
                context=context,
                trigger=data.trigger.value,
                event_seeds=data.event_seeds,
            )

            tasks = self._build_stream_tasks(
                context=context,
                events=events,
            )

            return PreparedDispatchState.ready(
                context=context,
                observer=observer,
                db_event_ids=[event.event_id for event in events],
                tasks=tasks,
            )

    def _check_dispatch_conflict(
        self,
        *,
        db: Session,
        data: PrepareDispatchInput,
    ):
        if data.sync_type != SyncType.FULL:
            return None

        if not try_acquire_full_sync_scope_lock(
            db,
            connector=data.connector,
            scope_id=data.scope_id,
        ):
            logger.info(
                "dispatch_conflict_lock_held",
                connector=data.connector.value,
                sync_type=data.sync_type.value,
                scope_id=data.scope_id,
            )
            return build_conflict_response(
                connector=data.connector,
                scope_id=data.scope_id,
                job_id=None,
                base_url=data.base_url,
                message="another full sync dispatch is already being created for this scope",
            )

        active_job = find_active_full_sync_job(
            db,
            connector=data.connector,
            scope_id=data.scope_id,
        )
        if active_job is None:
            return None

        logger.info(
            "dispatch_conflict_existing_job",
            connector=data.connector.value,
            sync_type=data.sync_type.value,
            scope_id=data.scope_id,
            active_job_id=active_job.job_id,
        )
        return build_conflict_response(
            connector=data.connector,
            scope_id=data.scope_id,
            job_id=active_job.job_id,
            base_url=data.base_url,
        )

    def _persist_events(
        self,
        *,
        db: Session,
        context: DispatchContext,
        event_seeds,
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
            raise SyncInternalException(
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
        context: DispatchContext,
        events: Sequence[SyncEvent],
    ):
        tasks = build_stream_tasks_from_persisted_events(
            events=events,
            fallback_scope_id=context.scope_id,
        )

        if len(tasks) != len(events):
            raise SyncInternalException(
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
