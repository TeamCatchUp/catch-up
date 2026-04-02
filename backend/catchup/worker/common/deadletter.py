from __future__ import annotations

from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.sync.stream_runtime.stream_queue import publish_deadletter
from catchup.worker.common.task import task_fields


async def deadletter(
    *,
    message: SyncStreamMessage,
    reason: SyncStreamFailureReason,
    error_message: str | None,
) -> None:
    await publish_deadletter(
        reason = reason,
        message_id = message.message_id,
        fields = task_fields(message.task),
        error_message = error_message,
    )