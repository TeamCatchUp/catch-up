from __future__ import annotations

from uuid import uuid4

from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import (
    SyncContext,
    SyncStreamMessage,
    SyncStreamTask,
)
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.sync.stream_runtime.stream_queue import publish_deadletter
from catchup.worker.handlers import get_ingestion_handler


def consumer_name() -> str:
    return f"sync-worker-{uuid4().hex[:8]}"


def task_fields(task: SyncStreamTask) -> dict[str, str]:
    return task.to_stream_fields()


# 같은 대상에 대한 중복처리를 방지하기 위한 Lock Key 생성 
def task_lock_key(task: SyncStreamTask) -> tuple[str, str, str, str]:
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
