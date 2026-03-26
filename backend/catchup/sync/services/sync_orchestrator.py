from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector, SyncEvent, SyncType
from catchup.db.sync import (
    SyncEventPublishResultInput,
    claim_events_for_publish,
    find_active_full_sync_job,
    record_event_publish_outcomes,
    try_acquire_full_sync_scope_lock,
)
from catchup.sync.common.exceptions import (
    RedisStreamPublishError,
    SyncInternalError,
    SyncRequestError,
)
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import (
    PublishTasksResult,
    SyncDispatchResult,
    SyncDispatchStatus,
    SyncEventSeed,
    SyncStreamTask,
    SyncTrigger,
)
from catchup.sync.event_publisher.event_record_persistence import (
    persist_sync_job_and_events,
)
from catchup.sync.event_publisher.stream_task_builder import (
    build_stream_tasks_from_persisted_events,
)
from catchup.sync.services.dispatch_observer import (
    DispatchObserverContext,
    SyncDispatchObserver,
    resolve_sync_dispatch_observer,
)
from catchup.sync.status_stream.pubsub import publish_job_status_event
from catchup.sync.status_stream.schemas import (
    SyncStatusEventType,
    SyncStatusStreamEvent,
    utc_now_iso,
)
logger = logging.getLogger(__name__)


def _build_job_urls(base_url: str | None, job_id: str) -> tuple[str | None, str | None]:
    if not base_url:
        return None, None

    base = base_url.rstrip("/")
    return (
        f"{base}/api/v1/sync/jobs/{job_id}",
        f"{base}/api/v1/sync/jobs/{job_id}/stream",
    )


def _build_job_queued_event(
    *,
    connector: SyncConnector,
    sync_type: SyncType,
    job_id: str,
    scope_id: str,
    total_targets: int,
    queued_targets: int,
    sync_from_ts: str | None,
) -> SyncStatusStreamEvent:
    payload: dict[str, object] = {
        "status": "pending",
        "sync_type": sync_type.value,
        "total_targets": total_targets,
        "queued_targets": queued_targets,
    }
    if sync_from_ts is not None:
        payload["sync_from_ts"] = sync_from_ts

    return SyncStatusStreamEvent(
        connector=connector,
        job_id=job_id,
        scope_id=scope_id,
        event_type=SyncStatusEventType.JOB_QUEUED,
        timestamp=utc_now_iso(),
        payload=payload,
    )


@dataclass(slots=True)
class PreparedDispatchState:
    context: DispatchObserverContext | None = None
    observer: SyncDispatchObserver | None = None
    db_event_ids: list[str] | None = None
    tasks: list[SyncStreamTask] | None = None
    conflict: SyncDispatchResult | None = None


class SyncDispatchOrchestrator:
    def __init__(
        self,
        event_publisher: EventPublisherProtocol,
        observer_resolver=resolve_sync_dispatch_observer,
    ):
        self._event_publisher = event_publisher
        self._observer_resolver = observer_resolver

    async def dispatch(
        self,
        *,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        trigger: SyncTrigger,
        event_seeds: list[SyncEventSeed],
        base_url: str | None,
        sync_from_ts: str | None = None,
    ) -> SyncDispatchResult:
        normalized_scope_id = self._normalize_scope_id(scope_id)

        no_events = self._build_no_events_response(
            connector=connector,
            scope_id=normalized_scope_id,
            total_targets=len(event_seeds),
        )
        if no_events is not None:
            return no_events

        prepared = await run_in_threadpool(
            self._prepare_dispatch_sync,
            connector,
            sync_type,
            normalized_scope_id,
            trigger,
            event_seeds,
            base_url,
        )

        if prepared.conflict is not None:
            return prepared.conflict

        context = prepared.context
        observer = prepared.observer
        db_event_ids = prepared.db_event_ids
        tasks = prepared.tasks

        if context is None or observer is None or db_event_ids is None or tasks is None:
            raise SyncInternalError("prepared dispatch state is incomplete")

        publish_result = await self._publish_dispatch_tasks(
            context=context,
            tasks=tasks,
            trigger=trigger,
            target_count=len(event_seeds),
            observer=observer,
        )

        await self._publish_queued_status(
            context=context,
            total_targets=len(event_seeds),
            queued_targets=publish_result.published_count,
            sync_from_ts=sync_from_ts,
        )

        return self._build_response(
            context=context,
            db_event_ids=db_event_ids,
            queued_targets=publish_result.published_count,
            base_url=base_url,
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

    def _build_no_events_response(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        total_targets: int,
    ) -> SyncDispatchResult | None:
        if total_targets != 0:
            return None

        logger.info(
            "[%s][ORCHESTRATOR] Dispatch skipped because no events were resolved: scope_id=%s",
            connector.value.upper(),
            scope_id,
        )
        return SyncDispatchResult(
            status=SyncDispatchStatus.NO_EVENTS,
            connector=connector,
            scope_id=scope_id,
            total_targets=0,
            queued_targets=0,
            message="no sync events were generated for this request",
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
            logger.warning(
                "[%s][%s][ORCHESTRATOR] Dispatch conflict while scope lock is held: scope_id=%s",
                connector.value.upper(),
                sync_type.value.upper(),
                scope_id,
            )
            return SyncDispatchResult(
                status=SyncDispatchStatus.CONFLICT,
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

        logger.warning(
            "[%s][%s][ORCHESTRATOR] Dispatch conflict due to active job: scope_id=%s, active_job_id=%s, active_status=%s",
            connector.value.upper(),
            sync_type.value.upper(),
            scope_id,
            active_job.job_id,
            active_job.status,
        )
        return self._build_conflict_response(
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

    def _prepare_dispatch_sync(
        self,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        trigger: SyncTrigger,
        event_seeds: list[SyncEventSeed],
        base_url: str | None,
    ) -> PreparedDispatchState:
        with SessionLocal() as db:
            # Full Sync 중복 Dispatch 확인
            conflict = self._check_dispatch_conflict(
                db=db,
                connector=connector,
                sync_type=sync_type,
                scope_id=scope_id,
                base_url=base_url,
            )
            if conflict is not None:
                db.rollback()
                return PreparedDispatchState(conflict=conflict)

            context = self._build_dispatch_context(
                connector=connector,
                sync_type=sync_type,
                scope_id=scope_id,
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

    async def _publish_tasks(
        self,
        *,
        tasks: list[SyncStreamTask],
    ) -> PublishTasksResult:
        return await self._event_publisher.publish(tasks=tasks)

    async def _publish_dispatch_tasks(
        self,
        *,
        context: DispatchObserverContext,
        tasks: list[SyncStreamTask],
        trigger: SyncTrigger,
        target_count: int,
        observer: SyncDispatchObserver,
    ) -> PublishTasksResult:
        if not tasks:
            return PublishTasksResult(
                requested_count=0,
                published_count=0,
                message_ids=[],
                partial_success=False,
            )

        await run_in_threadpool(
            self._claim_publish_records_sync,
            context,
            tasks,
        )

        try:
            publish_result = await self._publish_tasks(tasks=tasks)
        except Exception as exc:
            await run_in_threadpool(
                self._record_publish_failure_sync,
                context,
                tasks,
                str(exc),
            )
            observer.on_stream_publish_failed(
                context=context,
                trigger=trigger.value,
                target_count=target_count,
                error=exc,
            )
            raise

        await run_in_threadpool(
            self._record_publish_outcomes_sync,
            context,
            tasks,
            publish_result,
        )

        if publish_result.published_count != publish_result.requested_count:
            observer.on_stream_publish_failed(
                context=context,
                trigger=trigger.value,
                target_count=target_count,
                requested_count=publish_result.requested_count,
                published_count=publish_result.published_count,
            )
            raise RedisStreamPublishError(
                metadata={
                    "requested_count": publish_result.requested_count,
                    "published_count": publish_result.published_count,
                    "partial_success": publish_result.partial_success,
                    "failed_at_index": publish_result.failed_at_index,
                    "failed_event_id": publish_result.failed_event_id,
                    "error_message": publish_result.error_message,
                    "job_id": context.job_id,
                    "scope_id": context.scope_id,
                },
            )

        observer.on_stream_published(
            context=context,
            trigger=trigger.value,
            target_count=target_count,
            published_count=publish_result.published_count,
        )

        return publish_result

    def _claim_publish_records_sync(
        self,
        context: DispatchObserverContext,
        tasks: Sequence[SyncStreamTask],
    ) -> None:
        event_ids = [task.event_id for task in tasks]

        with SessionLocal() as db:
            try:
                if claim_events_for_publish(db, event_ids=event_ids):
                    db.commit()
                    return
            except Exception:
                db.rollback()
                raise

            db.rollback()
            raise SyncInternalError(
                "failed to transition events to publishing",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "event_ids": event_ids,
                },
            )

    def _record_publish_failure_sync(
        self,
        context: DispatchObserverContext,
        tasks: Sequence[SyncStreamTask],
        error_message: str,
    ) -> None:
        failed_event_ids = [task.event_id for task in tasks]

        with SessionLocal() as db:
            try:
                updated = record_event_publish_outcomes(
                    db,
                    published=[],
                    failed_event_ids=failed_event_ids,
                    publish_error=error_message,
                )
                if updated:
                    db.commit()
                    return
            except Exception:
                db.rollback()
                raise

            db.rollback()
            raise SyncInternalError(
                "failed to persist publish failure state",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "event_ids": failed_event_ids,
                    "error_message": error_message,
                },
            )

    def _record_publish_outcomes_sync(
        self,
        context: DispatchObserverContext,
        tasks: Sequence[SyncStreamTask],
        publish_result: PublishTasksResult,
    ) -> None:
        if publish_result.published_count != len(publish_result.message_ids):
            raise SyncInternalError(
                "publish result message count mismatch",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "published_count": publish_result.published_count,
                    "message_id_count": len(publish_result.message_ids),
                },
            )

        published = [
            SyncEventPublishResultInput(
                event_id=task.event_id,
                stream_message_id=message_id,
            )
            for task, message_id in zip(tasks, publish_result.message_ids)
        ]
        failed_event_ids = [
            task.event_id
            for task in tasks[len(publish_result.message_ids) :]
        ]

        with SessionLocal() as db:
            try:
                updated = record_event_publish_outcomes(
                    db,
                    published=published,
                    failed_event_ids=failed_event_ids,
                    publish_error=publish_result.error_message,
                )
                if updated:
                    db.commit()
                    return
            except Exception:
                db.rollback()
                raise

            db.rollback()
            raise SyncInternalError(
                "failed to persist publish result state",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "published_event_ids": [item.event_id for item in published],
                    "failed_event_ids": failed_event_ids,
                },
            )

    async def _publish_queued_status(
        self,
        *,
        context: DispatchObserverContext,
        total_targets: int,
        queued_targets: int,
        sync_from_ts: str | None,
    ) -> None:
        if total_targets == 0:
            return

        try:
            await publish_job_status_event(
                _build_job_queued_event(
                    connector=context.connector,
                    sync_type=context.sync_type,
                    job_id=context.job_id,
                    scope_id=context.scope_id,
                    total_targets=total_targets,
                    queued_targets=queued_targets,
                    sync_from_ts=sync_from_ts,
                )
            )
        except Exception as exc:
            logger.warning(
                "[%s][%s][ORCHESTRATOR] Failed to publish job queued status: scope_id=%s, job_id=%s, error=%s",
                context.connector.value.upper(),
                context.sync_type.value.upper(),
                context.scope_id,
                context.job_id,
                exc,
                exc_info=True,
            )

    def _build_response(
        self,
        *,
        context: DispatchObserverContext,
        db_event_ids: Sequence[str],
        queued_targets: int,
        base_url: str | None,
    ) -> SyncDispatchResult:
        snapshot_url, stream_url = _build_job_urls(base_url, context.job_id)

        logger.info(
            "[%s][%s][ORCHESTRATOR] Dispatch accepted: scope_id=%s, job_id=%s, total_targets=%s, queued_targets=%s",
            context.connector.value.upper(),
            context.sync_type.value.upper(),
            context.scope_id,
            context.job_id,
            len(db_event_ids),
            queued_targets,
        )

        return SyncDispatchResult(
            status=SyncDispatchStatus.ACCEPTED,
            connector=context.connector,
            scope_id=context.scope_id,
            job_id=context.job_id,
            event_ids=list(db_event_ids),
            total_targets=len(db_event_ids),
            queued_targets=queued_targets,
            message="sync dispatch accepted",
            snapshot_url=snapshot_url,
            stream_url=stream_url,
        )

    def _build_conflict_response(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        job_id: str | None,
        base_url: str | None,
    ) -> SyncDispatchResult:
        snapshot_url = None
        stream_url = None
        if job_id is not None:
            snapshot_url, stream_url = _build_job_urls(base_url, job_id)

        return SyncDispatchResult(
            status=SyncDispatchStatus.CONFLICT,
            connector=connector,
            scope_id=scope_id,
            job_id=job_id,
            message="active full sync already exists for this scope",
            snapshot_url=snapshot_url,
            stream_url=stream_url,
        )

    def _resolve_observer(
        self,
        context: DispatchObserverContext,
    ) -> SyncDispatchObserver:
        return self._observer_resolver(
            connector=context.connector,
            sync_type=context.sync_type,
        )
