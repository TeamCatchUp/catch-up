from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catchup.configs.config import settings
from catchup.connectors.slack.sync_runtime.constants import(
    SyncEventType,
    build_job_events_key,
    build_job_event_seq_key,
)
from catchup.connectors.slack.sync_runtime.schemas import SyncRuntimeEvent
from catchup.utils.redis import get_redis_client

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def next_sequence(job_id:str) -> int:
    redis = await get_redis_client()
    seq_key = build_job_event_seq_key(job_id)
    seq = await redis.incr(seq_key)
    await redis.expire(seq_key, settings.SYNC_JOB_EVENT_TTL_SECONDS)
    return int(seq)

async def append_event(
        *,
        job_id: str,
        team_id: str,
        event_type: SyncEventType,
        payload: dict[str, Any] | None = None,
) -> SyncRuntimeEvent:
    redis = await get_redis_client()
    events_key = build_job_events_key(job_id)

    event = SyncRuntimeEvent(
        job_id=job_id,
        team_id=team_id,
        event_type=event_type,
        sequence=await next_sequence(job_id),
        timestamp=_now_iso(),
        payload=payload or {},
    )

    await redis.rpush(events_key, event.to_event_log_payload())
    await redis.expire(events_key, settings.SYNC_JOB_EVENT_TTL_SECONDS)

    return event

async def get_events(job_id: str, start_sequence: int = 1) -> list[SyncRuntimeEvent]:
    redis = await get_redis_client()
    events_key = build_job_events_key(job_id)

    raw_items = await redis.lrange(events_key, 0, -1)
    if not raw_items:
        return []
    
    events: list[SyncRuntimeEvent] = []
    for raw in raw_items:
        payload = _decode(raw)
        event = SyncRuntimeEvent.from_event_log_payload(payload)
        if event.sequence >= start_sequence:
            events.append(event)

    events.sort(key=lambda item: item.sequence)
    return events

async def get_last_sequence(job_id: str) -> int:
    redis = await get_redis_client()
    seq_key = build_job_event_seq_key(job_id)
    value = await redis.get(seq_key)
    if value is None:
        return 0
    return int(_decode(value))


async def append_heartbeat(job_id: str, team_id: str) -> SyncRuntimeEvent:
    return await append_event(
        job_id=job_id,
        team_id=team_id,
        event_type=SyncEventType.HEARTBEAT,
        payload={},
    )
