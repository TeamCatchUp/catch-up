from __future__ import annotations

from typing import Sequence

from fastapi.concurrency import run_in_threadpool

from catchup.db.sync import SyncEventPublishResultInput
from catchup.db.sync import claim_events_for_publish
from catchup.db.sync import record_event_publish_outcomes
from catchup.sync.common.exceptions import RedisStreamPublishError
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import PublishTasksResult
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.dispatch.types import DispatchContext
from catchup.sync.dispatch.types import PublishDispatchInput
from catchup.db.engine import SessionLocal


class DispatchPublisher:
    def __init__(self, event_publisher: EventPublisherProtocol):
        self._event_publisher = event_publisher

    async def publish(self, data: PublishDispatchInput) -> PublishTasksResult:
        if not data.tasks:
            return PublishTasksResult(
                requested_count=0,
                published_count=0,
                message_ids=[],
                partial_success=False,
            )

        await run_in_threadpool(
            self._claim_publish_records_sync,
            data.context,
            data.tasks,
        )

        try:
            publish_result = await self._event_publisher.publish(tasks=data.tasks)
        except Exception as exc:
            await run_in_threadpool(
                self._record_publish_failure_sync,
                data.context,
                data.tasks,
                str(exc),
            )
            data.observer.on_stream_publish_failed(
                context=data.context,
                trigger=data.trigger.value,
                target_count=data.target_count,
                error=exc,
            )
            raise

        await run_in_threadpool(
            self._record_publish_outcomes_sync,
            data.context,
            data.tasks,
            publish_result,
        )

        if publish_result.published_count != publish_result.requested_count:
            data.observer.on_stream_publish_failed(
                context=data.context,
                trigger=data.trigger.value,
                target_count=data.target_count,
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
                    "job_id": data.context.job_id,
                    "scope_id": data.context.scope_id,
                },
            )

        data.observer.on_stream_published(
            context=data.context,
            trigger=data.trigger.value,
            target_count=data.target_count,
            published_count=publish_result.published_count,
        )

        return publish_result

    def _claim_publish_records_sync(
        self,
        context: DispatchContext,
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
        context: DispatchContext,
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
        context: DispatchContext,
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
            for task in tasks[len(publish_result.message_ids):]
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
