from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
from typing import Any

from catchup.db.models import SyncConnector, SyncJobStatus
from catchup.sync.status_stream.pubsub import (
    close_job_status_subscription,
    open_job_status_subscription,
    read_job_status_event,
)
from catchup.sync.status_stream.schemas import (
    SyncStatusEventType,
    SyncStatusStreamEvent,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

class SyncStatusStreamService:
    def _serialize_sse_event(self, event: SyncStatusStreamEvent) -> str:
        return f"event: {event.event_type.value}\ndata: {event.to_json()}\n\n"
    
    def _build_snapshot_event(
        self,
        *,
        snapshot: dict[str, Any],
    ) -> SyncStatusStreamEvent:
        connector = SyncConnector(str(snapshot["connector"]))
        job_id = str(snapshot["job_id"])
        scope_id = str(snapshot["scope_id"])
        status = SyncJobStatus(str(snapshot["status"]))

        return SyncStatusStreamEvent(
            connector=connector,
            job_id=job_id,
            scope_id=scope_id,
            event_type=SyncStatusEventType.SNAPSHOT,
            timestamp=utc_now_iso(),
            payload={
                "job_id": job_id,
                "connector": connector.value,
                "sync_type": str(snapshot["sync_type"]),
                "scope_id": scope_id,
                "status": status.value,
                "created_at": snapshot["created_at"],
                "started_at": snapshot["started_at"],
                "completed_at": snapshot["completed_at"],
                "total_targets": int(snapshot["total_targets"]),
                "queued_targets": int(snapshot["queued_targets"]),
                "processing_targets": int(snapshot["processing_targets"]),
                "completed_targets": int(snapshot["completed_targets"]),
                "failed_targets": int(snapshot["failed_targets"]),
                "requeued_targets": int(snapshot["requeued_targets"]),
                "metrics": dict(snapshot.get("metrics") or {}),
                "last_error": snapshot.get("last_error"),
            },
        )

    def _build_heartbeat_event(
        self,
        *,
        connector: SyncConnector,
        job_id: str,
        scope_id: str,
    ) -> SyncStatusStreamEvent:
        return SyncStatusStreamEvent(
            connector=connector,
            job_id=job_id,
            scope_id=scope_id,
            event_type=SyncStatusEventType.HEARTBEAT,
            timestamp=utc_now_iso(),
            payload={},
        )

    def _is_terminal_event(self, event: SyncStatusStreamEvent) -> bool:
        return event.event_type in {
            SyncStatusEventType.JOB_COMPLETED,
            SyncStatusEventType.JOB_FAILED,
        }
    
    
    async def stream_job_events_sse(
        self,
        *,
        snapshot: dict[str, Any],
        heartbeat_seconds: int,
    ) -> AsyncGenerator[str, None]:
        # 라우터에서 조회한 첫 스냅샷을 첫번쨰 SSE 이벤트로 사용
        snapshot_event = self._build_snapshot_event(snapshot=snapshot)

        pubsub = None
        channel = None

        try:
            # job_id를 통해서 PubSub에 채널을 개설
            pubsub, channel = await open_job_status_subscription(snapshot_event.job_id)


            yield self._serialize_sse_event(snapshot_event)

            while True:
                try:
                    event = await read_job_status_event(
                        pubsub,
                        timeout_seconds=max(1, heartbeat_seconds),
                    )
                except Exception:
                    logger.exception(
                        "[SYNC][STATUS][STREAM] Failed to read pubsub event: job_id=%s",
                        snapshot_event.job_id,
                    )
                    break

                if event is None:
                    yield self._serialize_sse_event(
                        self._build_heartbeat_event(
                            connector=snapshot_event.connector,
                            job_id=snapshot_event.job_id,
                            scope_id=snapshot_event.scope_id,
                        )
                    )
                    continue

                yield self._serialize_sse_event(event)

                if self._is_terminal_event(event):
                    break

        finally:
            if pubsub is not None and channel is not None:
                try:
                    await close_job_status_subscription(pubsub, channel)
                except Exception:
                    logger.exception(
                        "[SYNC][STATUS][STREAM] Failed to close pubsub subscription: job_id=%s",
                        snapshot_event.job_id,
                    )


_sync_status_stream_service = SyncStatusStreamService()


def get_sync_status_stream_service() -> SyncStatusStreamService:
    return _sync_status_stream_service