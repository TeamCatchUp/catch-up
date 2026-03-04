from __future__ import annotations

from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.stream_runtime.stream_queue import publish_tasks
from catchup.sync.stream_runtime.sync_runtime import initialize_stream_runtime


class RedisStreamEventPublisher(EventPublisherProtocol):
    """Redis Stream publish만 담당하는 EventPublisher 어댑터."""

    async def publish(self, *, tasks: list[SyncStreamTask]) -> list[str]:
        if not tasks:
            return []
        await initialize_stream_runtime()
        return await publish_tasks(tasks)


_event_publisher = RedisStreamEventPublisher()


def get_event_publisher() -> EventPublisherProtocol:
    return _event_publisher
