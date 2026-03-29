from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
import structlog

from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.dispatch.preparer import DispatchPreparer
from catchup.sync.dispatch.publisher import DispatchPublisher
from catchup.sync.dispatch.result_builder import build_accepted_response
from catchup.sync.dispatch.result_builder import build_no_events_response
from catchup.sync.dispatch.types import DispatchRequest
from catchup.sync.dispatch.types import PrepareDispatchInput
from catchup.sync.dispatch.types import PublishDispatchInput

logger = structlog.get_logger(__name__)


class DispatchService:
    def __init__(self, event_publisher: EventPublisherProtocol):
        self._preparer = DispatchPreparer()
        self._publisher = DispatchPublisher(event_publisher=event_publisher)

    async def dispatch(self, request: DispatchRequest) -> SyncDispatchResult:
        if not request.event_seeds:
            logger.info(
                "no_events_to_dispatch",
                connector=request.connector.value,
                scope_id=request.scope_id,
            )
            return build_no_events_response(
                connector=request.connector,
                scope_id=request.scope_id,
            )

        prepared = await run_in_threadpool(
            self._preparer.prepare,
            PrepareDispatchInput.from_request(request),
        )

        if prepared.conflict is not None:
            return prepared.conflict

        context = prepared.context
        observer = prepared.observer
        db_event_ids = prepared.db_event_ids
        tasks = prepared.tasks

        if context is None or observer is None or db_event_ids is None or tasks is None:
            raise SyncInternalError("prepared dispatch state is incomplete")

        publish_result = await self._publisher.publish(
            PublishDispatchInput.from_request(
                request,
                context=context,
                tasks=tasks,
                observer=observer,
            ),
        )

        logger.info(
            "dispatch_accepted",
            connector=context.connector.value,
            sync_type=context.sync_type.value,
            scope_id=context.scope_id,
            job_id=context.job_id,
            total_targets=len(db_event_ids),
            queued_targets=publish_result.published_count,
        )

        return build_accepted_response(
            context=context,
            db_event_ids=db_event_ids,
            queued_targets=publish_result.published_count,
            base_url=request.base_url,
        )
