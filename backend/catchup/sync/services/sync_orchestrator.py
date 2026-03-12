from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector, SyncType
from catchup.db.sync import (
    SyncEventPublishResultInput,
    claim_events_for_publish,
    complete_job_success as complete_db_sync_job_success,
    record_event_publish_outcomes,
    start_job as start_db_sync_job,
)
from catchup.sync.common.exceptions import RedisStreamPublishError, SyncInternalError
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
    build_stream_tasks_from_event_ids,
)
from catchup.sync.status_stream.pubsub import publish_job_status_event
from catchup.sync.status_stream.schemas import (
    SyncStatusEventType,
    SyncStatusStreamEvent,
    utc_now_iso,
)
from catchup.sync.sync_audit import emit_sync_dispatch_accepted

logger = logging.getLogger(__name__)

@dataclass(slots=True, frozen=True)
class DispatchContext:
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    job_id: str
    requested_at: datetime


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


class SyncDispatchOrchestrator:
    def __init__(self, event_publisher: EventPublisherProtocol):
        self._event_publisher = event_publisher

    async def dispatch(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
        trigger: SyncTrigger,
        event_seeds: list[SyncEventSeed],
        base_url: str | None,
        sync_from_ts: str | None = None,
    ) -> SyncDispatchResult:
        # Scope 정규화
        normalized_scope_id = self._normalize_scope_id(scope_id)
        
        context = self._build_dispatch_context(
            connector=connector,
            sync_type=sync_type,
            scope_id=normalized_scope_id,
        )

        # DB에 Job & Event 기록
        db_event_ids = self._persist_dispatch_records(
            db=db,
            context=context,
            event_seeds=event_seeds,
        )

        # Redis Stream에 저장할 Task 생성
        tasks = self._build_stream_tasks(
            context=context,
            event_seeds=event_seeds,
            db_event_ids=db_event_ids,
        )
        # Event Publisher를 통해 Redis Stream에 이벤트 발행
        publish_result = await self._publish_dispatch_tasks(
            db=db,
            context=context,
            tasks=tasks,
        )

        # PubSub에 Job Accepted 이벤트 발행
        await self._publish_queued_status(
            context=context,
            total_targets=len(event_seeds),
            queued_targets=publish_result.published_count,
            sync_from_ts=sync_from_ts,
        )

        # 처리할 대상이 없는 Job이였다면 즉시 성공 처리
        self._finalize_empty_job(
            db=db,
            job_id=context.job_id,
            total_targets=len(event_seeds),
        )
        
        # 로깅
        self._emit_dispatch_audit(
            context=context,
            trigger=trigger,
            total_targets=len(event_seeds),
            queued_targets=publish_result.published_count,
        )

        # 응답 반환
        return self._build_response(
            context=context,
            db_event_ids=db_event_ids,
            queued_targets=publish_result.published_count,
            base_url=base_url,
        )

    def _normalize_scope_id(self, scope_id: str) -> str:
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise ValueError("scope_id is required")
        return normalized_scope_id

    def _build_dispatch_context(
        self,
        *,
        connector: SyncConnector,
        sync_type: SyncType,
        scope_id: str,
    ) -> DispatchContext:
        return DispatchContext(
            connector=connector,
            sync_type=sync_type,
            scope_id=scope_id,
            job_id=uuid4().hex,
            requested_at=datetime.now(timezone.utc),
        )

    def _persist_events(
        self,
        *,
        db: Session,
        context: DispatchContext,
        event_seeds: Sequence[SyncEventSeed],
    ) -> list[str]:
        db_event_ids = persist_sync_job_and_events(
            db,
            job_id=context.job_id,
            connector=context.connector,
            sync_type=context.sync_type,
            scope_id=context.scope_id,
            requested_at=context.requested_at,
            event_seeds=list(event_seeds),
        )

        if len(db_event_ids) != len(event_seeds):
            raise SyncInternalError(
                "persisted event count mismatch",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "requested_event_count": len(event_seeds),
                    "persisted_event_count": len(db_event_ids),
                },
            )

        return db_event_ids
    
    def _persist_dispatch_records(
        self,
        *,
        db: Session,
        context: DispatchContext,
        event_seeds: Sequence[SyncEventSeed],
    ) -> list[str]:
        try:
            db_event_ids = self._persist_events(
                db=db,
                context=context,
                event_seeds=event_seeds
            )
            db.commit()
            return db_event_ids
        except Exception:
            db.rollback()
            raise

    def _build_stream_tasks(
        self,
        *,
        context: DispatchContext,
        event_seeds: Sequence[SyncEventSeed],
        db_event_ids: Sequence[str],
    ) -> list[SyncStreamTask]:
        tasks = build_stream_tasks_from_event_ids(
            event_ids=list(db_event_ids),
            job_id=context.job_id,
            connector=context.connector,
            sync_type=context.sync_type,
            scope_id=context.scope_id,
            event_seeds=list(event_seeds),
        )

        if len(tasks) != len(db_event_ids):
            raise SyncInternalError(
                "stream task build count mismatch",
                metadata={
                    "connector": context.connector.value,
                    "sync_type": context.sync_type.value,
                    "scope_id": context.scope_id,
                    "job_id": context.job_id,
                    "persisted_event_count": len(db_event_ids),
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
        db: Session,
        context: DispatchContext,
        tasks: list[SyncStreamTask],
    ) -> PublishTasksResult:
        if not tasks:
            return PublishTasksResult(
                requested_count=0,
                published_count=0,
                message_ids=[],
                partial_success=False,
            )

        self._claim_publish_records(
            db=db,
            context=context,
            tasks=tasks,
        )

        try:
            publish_result = await self._publish_tasks(tasks=tasks)
        except Exception as exc:
            self._record_publish_failure(
                db=db,
                context=context,
                tasks=tasks,
                error_message=str(exc),
            )
            raise

        self._record_publish_outcomes(
            db=db,
            context=context,
            tasks=tasks,
            publish_result=publish_result,
        )

        if publish_result.published_count != publish_result.requested_count:
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

        return publish_result

    def _claim_publish_records(
        self,
        *,
        db: Session,
        context: DispatchContext,
        tasks: Sequence[SyncStreamTask],
    ) -> None:
        event_ids = [task.event_id for task in tasks]
        if claim_events_for_publish(db, event_ids=event_ids):
            return

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

    def _record_publish_failure(
        self,
        *,
        db: Session,
        context: DispatchContext,
        tasks: Sequence[SyncStreamTask],
        error_message: str,
    ) -> None:
        failed_event_ids = [task.event_id for task in tasks]
        updated = record_event_publish_outcomes(
            db,
            published=[],
            failed_event_ids=failed_event_ids,
            publish_error=error_message,
        )
        if updated:
            return

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

    def _record_publish_outcomes(
        self,
        *,
        db: Session,
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
            for task in tasks[len(publish_result.message_ids) :]
        ]

        updated = record_event_publish_outcomes(
            db,
            published=published,
            failed_event_ids=failed_event_ids,
            publish_error=publish_result.error_message,
        )
        if updated:
            return

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
        context: DispatchContext,
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

    def _finalize_empty_job(
        self,
        *,
        db: Session,
        job_id: str,
        total_targets: int,
    ) -> None:
        if total_targets != 0:
            return

        started = start_db_sync_job(db, job_id)
        if started:
            complete_db_sync_job_success(db, job_id)

    def _emit_dispatch_audit(
        self,
        *,
        context: DispatchContext,
        trigger: SyncTrigger,
        total_targets: int,
        queued_targets: int,
    ) -> None:
        emit_sync_dispatch_accepted(
            connector=context.connector,
            sync_type=context.sync_type,
            trigger=trigger.value,
            run_id=context.job_id,
            scope_id=context.scope_id,
            counts={
                "total_targets": total_targets,
                "queued_targets": queued_targets,
            },
        )

    def _build_response(
        self,
        *,
        context: DispatchContext,
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
            snapshot_url=snapshot_url,
            stream_url=stream_url,
        )
