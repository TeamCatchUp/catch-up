from __future__ import annotations

from typing import Any

from catchup.sync.status_stream.constants import build_job_status_channel
from catchup.sync.status_stream.schemas import SyncStatusStreamEvent
from catchup.utils.redis import get_redis_client


def _decode_pubsub_data(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)

async def publish_job_status_event(event: SyncStatusStreamEvent) -> None:
    redis = await get_redis_client()
    channel = build_job_status_channel(event.job_id)
    await redis.publish(channel, event.to_json())


async def open_job_status_subscription(job_id: str) -> tuple[Any, str]:
    redis = await get_redis_client()
    channel = build_job_status_channel(job_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    return pubsub, channel

async def close_job_status_subscription(pubsub: Any, channel:str) -> None:
    try:
        await pubsub.unsubscribe(channel)
    finally:
        await pubsub.aclose()

async def read_job_status_event(
    pubsub: Any,
    timeout_seconds: float | None,
) -> SyncStatusStreamEvent | None:
    message = await pubsub.get_message(
        ignore_subscribe_messages = False,
        timeout = timeout_seconds
    )

    if not message:
        return None
    
    message_type = str(message.get("type") or "")
    if message_type != "message":
        return None
    
    raw_data = _decode_pubsub_data(message.get("data"))
    return SyncStatusStreamEvent.from_json(raw_data)