from __future__ import annotations

import logging
from uuid import uuid4

from catchup.db.models import SyncType
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncContext
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.status_stream.schemas import SyncStatusEventType
from catchup.sync.status_stream.schemas import SyncStatusStreamEvent
from catchup.sync.status_stream.schemas import utc_now_iso
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.sync.stream_runtime.stream_queue import publish_deadletter
from catchup.worker.handlers import get_ingestion_handler

logger = logging.getLogger(__name__)


def consumer_name() -> str:
    return f"sync-worker-{uuid4().hex[:8]}"


def task_fields(task: SyncStreamTask) -> dict[str, str]:
    return task.to_stream_fields()


# 같은 대상에 대한 중복처리를 방지하기 위한 Lock Key 생성
def task_lock_key(task: SyncStreamTask) -> tuple[str, ...]:
    if task.sync_type == SyncType.FULL:
        stage = (task.stage or "").strip()
        target_id = (task.target_id or "").strip() or task.event_id
        base_key = (
            task.connector.strip(),
            (task.scope_id or "").strip(),
            target_id,
            stage,
        )

        range_start = (task.range_start or "").strip()
        range_end = (task.range_end or "").strip()
        if range_start and range_end:
            return base_key + (range_start, range_end)

        chunk_index = task.chunk_index
        chunk_total = task.chunk_total
        if chunk_index is not None and chunk_total is not None:
            return base_key + (str(chunk_index), str(chunk_total))

        return base_key

    target_type = (
        (task.target_type or "").strip()
        or ("record" if task.record_key else "event")
    )
    target_id = (
        (task.target_id or "").strip()
        or (task.record_key or "").strip()
        or task.event_id
    )
    return (
        task.connector.strip(),
        (task.scope_id or "").strip(),
        target_type,
        target_id,
    )

def select_handler(context: SyncContext) -> IngestionHandlerProtocol | None:
    return get_ingestion_handler(
        connector=context.connector,
        sync_type=context.sync_type,
    )


def build_target_status_event(
    *,
    context: SyncContext,
    event_type: SyncStatusEventType,
    status: str,
    attempt: int | None = None,
    extra_payload: dict[str, object] | None = None,
) -> SyncStatusStreamEvent:
    payload: dict[str, object] = {
        "sync_type": context.sync_type,
        "event_id": context.event_id,
        "target_type": context.target_type,
        "target_id": context.target_id,
        "target_name": context.target_name,
        "status": status,
        "attempt": context.attempt if attempt is None else attempt,
        "max_attempts": context.max_attempts,
    }
    if extra_payload:
        payload.update(extra_payload)

    return SyncStatusStreamEvent(
        connector=context.connector,
        job_id=context.job_id,
        scope_id=context.scope_id,
        event_type=event_type,
        timestamp=utc_now_iso(),
        payload=payload,
    )


def build_job_status_event(
    *,
    context: FullSyncContext,
    event_type: SyncStatusEventType,
    status: str,
    total_targets: int,
    completed_targets: int | None = None,
    failed_targets: int | None = None,
    requeued_targets: int | None = None,
) -> SyncStatusStreamEvent:
    payload: dict[str, object] = {
        "sync_type": context.sync_type,
        "status": status,
        "total_targets": total_targets,
    }
    if completed_targets is not None:
        payload["completed_targets"] = completed_targets
    if failed_targets is not None:
        payload["failed_targets"] = failed_targets
    if requeued_targets is not None:
        payload["requeued_targets"] = requeued_targets

    return SyncStatusStreamEvent(
        connector=context.connector,
        job_id=context.job_id,
        scope_id=context.scope_id,
        event_type=event_type,
        timestamp=utc_now_iso(),
        payload=payload,
    )


# Status Streaming이 Sync 흐름을 막지 않도록 로그만 남김
async def publish_status_event(event: SyncStatusStreamEvent) -> None:
    # NOTE:
    # Sync status SSE stream is currently unused, so Redis Pub/Sub publish is
    # intentionally disabled while keeping the implementation reusable.
    # try:
    #     await publish_job_status_event(event)
    # except Exception as exc:
    #     logger.warning(
    #         "[SYNC][STATUS][WORKER] Failed to publish status event: job_id=%s, event_type=%s, error=%s",
    #         event.job_id,
    #         event.event_type.value,
    #         exc,
    #         exc_info=True,
    #     )
    return None


# 최종 실패 event를 DLQ 처리함
async def deadletter(
    *,
    message: SyncStreamMessage,
    reason: SyncStreamFailureReason,
    error_message: str | None,
) -> None:
    await publish_deadletter(
        reason=reason,
        message_id=message.message_id,
        fields=task_fields(message.task),
        error_message=error_message,
    )
