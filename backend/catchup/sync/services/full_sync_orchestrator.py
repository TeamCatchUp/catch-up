from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.models import SyncConnector, SyncType
from catchup.db.sync import (
    complete_job_success as complete_db_sync_job_success,
    start_job as start_db_sync_job,
)
from catchup.sync.common.protocols import (
    EventPublisherProtocol,
    FullSyncTargetResolverProtocol,
)
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    SyncDispatchResult,
    SyncEventSeed,
)
from catchup.sync.event_publisher.common_event_builder import (
    build_stream_tasks_from_event_ids,
    persist_sync_job_and_events,
)
from catchup.sync.sync_audit import emit_sync_dispatch_accepted

logger = logging.getLogger(__name__)


def _build_job_urls(base_url: str | None, job_id: str) -> tuple[str | None, str | None]:
    if not base_url:
        return None, None

    base = base_url.rstrip("/")
    return (
        f"{base}/api/v1/sync/jobs/{job_id}",
        f"{base}/api/v1/sync/jobs/{job_id}/stream",
    )


class FullSyncDispatchOrchestrator:
    def __init__(self, event_publisher: EventPublisherProtocol):
        self._event_publisher = event_publisher

    async def dispatch(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
        base_url: str | None,
        resolver: FullSyncTargetResolverProtocol,
    ) -> SyncDispatchResult:
        scope_id = request.scope_id
        sync_days = request.sync_days or settings.DEFAULT_SYNC_DAYS
        requested_at = datetime.now(timezone.utc)
        sync_from = str((requested_at - timedelta(days=sync_days)).timestamp())
        job_id = uuid4().hex

        resolved = await resolver.resolve_full_sync_targets(
            db=db,
            request=request,
            sync_from=sync_from,
        )

        event_seeds: list[SyncEventSeed] = []
        for target in resolved.targets:
            normalized_target_id = target.target_id.strip()
            if not normalized_target_id:
                continue

            normalized_target_type = target.target_type.strip() or "resource"
            normalized_target_name = target.target_name.strip() or normalized_target_id

            metadata = dict(target.metadata)
            metadata.setdefault("sync_from", sync_from)

            event_seeds.append(
                SyncEventSeed(
                    event_id=uuid4().hex,
                    target_type=normalized_target_type,
                    target_id=normalized_target_id,
                    target_name=normalized_target_name,
                    metadata=metadata,
                    max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
                )
            )

        total_targets = len(event_seeds)

        db_event_ids = persist_sync_job_and_events(
            db,
            job_id=job_id,
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            requested_at=requested_at,
            event_seeds=event_seeds,
            scope_metadata=resolved.scope_metadata,
        )
        if len(db_event_ids) != total_targets:
            logger.warning(
                "[%s][FULL SYNC][ORCHESTRATOR] Persisted event count mismatch: scope_id=%s, job_id=%s, target_count=%s, persisted_event_count=%s",
                connector.value.upper(),
                scope_id,
                job_id,
                total_targets,
                len(db_event_ids),
            )

        tasks = build_stream_tasks_from_event_ids(
            event_ids=db_event_ids,
            job_id=job_id,
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            event_seeds=event_seeds,
        )
        if len(tasks) != len(db_event_ids):
            logger.warning(
                "[%s][FULL SYNC][ORCHESTRATOR] Stream task build mismatch: scope_id=%s, job_id=%s, persisted_event_count=%s, built_task_count=%s",
                connector.value.upper(),
                scope_id,
                job_id,
                len(db_event_ids),
                len(tasks),
            )

        message_ids = await self._event_publisher.publish(tasks=tasks)
        if len(message_ids) != len(tasks):
            logger.warning(
                "[%s][FULL SYNC][ORCHESTRATOR] Publish result mismatch: scope_id=%s, job_id=%s, task_count=%s, published_message_count=%s",
                connector.value.upper(),
                scope_id,
                job_id,
                len(tasks),
                len(message_ids),
            )

        if total_targets == 0:
            started = start_db_sync_job(db, job_id)
            if started:
                complete_db_sync_job_success(db, job_id)

        snapshot_url, stream_url = _build_job_urls(base_url, job_id)

        logger.info(
            "[%s][FULL SYNC][ORCHESTRATOR] Dispatch accepted: scope_id=%s, job_id=%s, total_targets=%s, queued_targets=%s, invalid_target_count=%s, sync_days=%s",
            connector.value.upper(),
            scope_id,
            job_id,
            total_targets,
            len(message_ids),
            len(resolved.invalid_target_ids),
            sync_days,
        )
        emit_sync_dispatch_accepted(
            connector=connector,
            sync_type=SyncType.FULL,
            trigger=request.trigger,
            run_id=job_id,
            scope_id=scope_id,
            counts={
                "total_targets": total_targets,
                "queued_targets": len(message_ids),
                "dropped_targets": len(resolved.invalid_target_ids),
                "dropped_events": max(0, total_targets - len(message_ids)),
            },
            scope_metadata=resolved.scope_metadata,
        )

        return SyncDispatchResult(
            status="accepted",
            connector=connector,
            scope_id=scope_id,
            job_id=job_id,
            event_ids=db_event_ids,
            total_targets=total_targets,
            queued_targets=len(message_ids),
            dropped_targets=len(resolved.invalid_target_ids),
            dropped_events=max(0, total_targets - len(message_ids)),
            snapshot_url=snapshot_url,
            stream_url=stream_url,
        )
