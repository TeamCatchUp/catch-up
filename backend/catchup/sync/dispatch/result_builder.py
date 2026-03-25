from __future__ import annotations

import logging

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncDispatchStatus
from catchup.sync.dispatch.observer import DispatchObserverContext
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.sync.status_stream.schemas import SyncStatusStreamEvent
from catchup.sync.status_stream.schemas import utc_now_iso

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


class DispatchResultBuilder:
    def build_no_events_response(
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

    async def publish_queued_status(
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
            # NOTE:
            # Sync status SSE stream is currently unused, so Redis Pub/Sub
            # publish is intentionally disabled while keeping the implementation
            # reusable.
            # await publish_job_status_event(
            #     _build_job_queued_event(
            #         connector=context.connector,
            #         sync_type=context.sync_type,
            #         job_id=context.job_id,
            #         scope_id=context.scope_id,
            #         total_targets=total_targets,
            #         queued_targets=queued_targets,
            #         sync_from_ts=sync_from_ts,
            #     )
            # )
            return
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

    def build_response(
        self,
        *,
        context: DispatchObserverContext,
        db_event_ids: list[str],
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

    def build_conflict_response(
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
