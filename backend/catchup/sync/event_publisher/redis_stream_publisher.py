from __future__ import annotations

import logging

from catchup.sync.common.exceptions import RedisStreamInitializationError
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import PublishTasksResult, SyncStreamTask
from catchup.sync.stream_runtime.stream_queue import publish_tasks
from catchup.sync.stream_runtime.sync_runtime import initialize_stream_runtime

logger = logging.getLogger(__name__)


class RedisStreamEventPublisher(EventPublisherProtocol):
    """Redis Stream publish만 담당하는 EventPublisher 어댑터."""

    async def publish(self, *, tasks: list[SyncStreamTask]) -> PublishTasksResult:
        if not tasks:
            return PublishTasksResult(
                requested_count=0,
                published_count=0,
                message_ids=[],
                partial_success=False,
            )
        try:
            await initialize_stream_runtime()
        except Exception as exc:
            logger.error(
                "[SYNC][STREAM][PUBLISHER] Runtime initialization failed: requested_count=%s, error=%s",
                len(tasks),
                exc,
                exc_info=True,
            )
            raise RedisStreamInitializationError(
                metadata={
                    "requested_count": len(tasks),
                    "error_message": str(exc),
                },
            ) from exc

        publish_result = await publish_tasks(tasks)
        if publish_result.published_count != publish_result.requested_count:
            logger.error(
                "[SYNC][STREAM][PUBLISHER] Publish failed: requested_count=%s, published_count=%s, partial_success=%s, failed_at_index=%s, failed_event_id=%s, error=%s",
                publish_result.requested_count,
                publish_result.published_count,
                publish_result.partial_success,
                publish_result.failed_at_index,
                publish_result.failed_event_id,
                publish_result.error_message,
            )

        return publish_result


_event_publisher = RedisStreamEventPublisher()


def get_event_publisher() -> EventPublisherProtocol:
    return _event_publisher
