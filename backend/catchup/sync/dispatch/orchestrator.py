from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncEventSeed
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.common.schemas import SyncTrigger
from catchup.sync.dispatch.observer import DispatchObserverContext
from catchup.sync.dispatch.observer import SyncDispatchObserver
from catchup.sync.dispatch.observer import resolve_sync_dispatch_observer
from catchup.sync.dispatch.preparer import DispatchPreparer
from catchup.sync.dispatch.preparer import PreparedDispatchState
from catchup.sync.dispatch.publisher import DispatchPublisher
from catchup.sync.dispatch.result_builder import DispatchResultBuilder
from catchup.sync.dispatch.result_builder import _build_job_queued_event
from catchup.sync.dispatch.result_builder import _build_job_urls


class SyncDispatchOrchestrator:
    def __init__(
        self,
        event_publisher: EventPublisherProtocol,
        observer_resolver=resolve_sync_dispatch_observer,
    ):
        self._observer_resolver = observer_resolver
        self._result_builder = DispatchResultBuilder()
        self._preparer = DispatchPreparer(
            observer_resolver=observer_resolver,
            result_builder=self._result_builder,
        )
        self._publisher = DispatchPublisher(event_publisher)

    def _normalize_scope_id(self, scope_id: str) -> str:
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise SyncRequestError("scope_id is required")
        return normalized_scope_id

    def _build_no_events_response(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        total_targets: int,
    ) -> SyncDispatchResult | None:
        return self._result_builder.build_no_events_response(
            connector=connector,
            scope_id=scope_id,
            total_targets=total_targets,
        )

    def _prepare_dispatch_sync(
        self,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        trigger: SyncTrigger,
        event_seeds: list[SyncEventSeed],
        base_url: str | None,
    ) -> PreparedDispatchState:
        return self._preparer.prepare(
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
            trigger=trigger,
            event_seeds=event_seeds,
            base_url=base_url,
        )

    def _build_dispatch_context(
        self,
        *,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
    ) -> DispatchObserverContext:
        return self._preparer._build_dispatch_context(
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
        )

    def _check_dispatch_conflict(
        self,
        *,
        db,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        base_url: str | None,
    ):
        return self._preparer._check_dispatch_conflict(
            db=db,
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
            base_url=base_url,
        )

    def _persist_events(
        self,
        *,
        db,
        context: DispatchObserverContext,
        event_seeds: list[SyncEventSeed],
    ):
        return self._preparer._persist_events(
            db=db,
            context=context,
            event_seeds=event_seeds,
        )

    def _build_stream_tasks(
        self,
        *,
        context: DispatchObserverContext,
        events,
    ) -> list[SyncStreamTask]:
        return self._preparer._build_stream_tasks(
            context=context,
            events=events,
        )

    async def _publish_tasks(self, *, tasks: list[SyncStreamTask]):
        return await self._publisher._event_publisher.publish(tasks=tasks)

    async def _publish_dispatch_tasks(
        self,
        *,
        context: DispatchObserverContext,
        tasks: list[SyncStreamTask],
        trigger: SyncTrigger,
        target_count: int,
        observer: SyncDispatchObserver,
    ):
        return await self._publisher.publish(
            context=context,
            tasks=tasks,
            trigger=trigger,
            target_count=target_count,
            observer=observer,
        )

    def _claim_publish_records_sync(
        self,
        context: DispatchObserverContext,
        tasks: list[SyncStreamTask],
    ) -> None:
        self._publisher._claim_publish_records_sync(context, tasks)

    def _record_publish_failure_sync(
        self,
        context: DispatchObserverContext,
        tasks: list[SyncStreamTask],
        error_message: str,
    ) -> None:
        self._publisher._record_publish_failure_sync(
            context=context,
            tasks=tasks,
            error_message=error_message,
        )

    def _record_publish_outcomes_sync(
        self,
        context: DispatchObserverContext,
        tasks: list[SyncStreamTask],
        publish_result,
    ) -> None:
        self._publisher._record_publish_outcomes_sync(
            context=context,
            tasks=tasks,
            publish_result=publish_result,
        )

    async def _publish_queued_status(
        self,
        *,
        context: DispatchObserverContext,
        total_targets: int,
        queued_targets: int,
        sync_from_ts: str | None,
    ) -> None:
        await self._result_builder.publish_queued_status(
            context=context,
            total_targets=total_targets,
            queued_targets=queued_targets,
            sync_from_ts=sync_from_ts,
        )

    def _build_conflict_response(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        job_id: str | None,
        base_url: str | None,
    ) -> SyncDispatchResult:
        return self._result_builder.build_conflict_response(
            connector=connector,
            scope_id=scope_id,
            job_id=job_id,
            base_url=base_url,
        )

    def _build_response(
        self,
        *,
        context: DispatchObserverContext,
        db_event_ids: list[str],
        queued_targets: int,
        base_url: str | None,
    ) -> SyncDispatchResult:
        return self._result_builder.build_response(
            context=context,
            db_event_ids=db_event_ids,
            queued_targets=queued_targets,
            base_url=base_url,
        )

    def _resolve_observer(
        self,
        context: DispatchObserverContext,
    ) -> SyncDispatchObserver:
        return self._observer_resolver(
            connector=context.connector,
            sync_type=context.sync_type,
        )

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
            connector=connector,
            sync_type=sync_type,
            scope_id=normalized_scope_id,
            trigger=trigger,
            event_seeds=event_seeds,
            base_url=base_url,
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


__all__ = [
    "PreparedDispatchState",
    "SyncDispatchOrchestrator",
    "_build_job_queued_event",
    "_build_job_urls",
]
