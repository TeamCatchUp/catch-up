from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Mapping

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from catchup.configs.config import settings
from catchup.sync.stream_runtime.stream_constants import STREAM_CLAIM_START_ID
from catchup.sync.stream_runtime.stream_constants import STREAM_READ_NEW_MESSAGE_ID
from catchup.sync.stream_runtime.stream_constants import SYNC_EVENTS_CONSUMER_GROUP
from catchup.sync.stream_runtime.stream_constants import (
    SYNC_EVENTS_DEADLETTER_STREAM_KEY,
)
from catchup.sync.stream_runtime.stream_constants import SYNC_EVENTS_STREAM_KEY
from catchup.sync.stream_runtime.stream_constants import SyncStreamFailureReason
from catchup.sync.stream_runtime.stream_schemas import PublishTasksResult
from catchup.sync.stream_runtime.stream_schemas import SyncClaimBatch
from catchup.sync.stream_runtime.stream_schemas import SyncStreamMessage
from catchup.sync.stream_runtime.stream_schemas import SyncStreamTask
from catchup.utils.redis import get_redis_client
from catchup.utils.redis import get_stream_redis_client
from catchup.utils.redis import reset_stream_redis_client

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class AckDeleteResult:
    acked: int
    deleted: int


def _decode_redis_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _normalize_stream_fields(raw_fields: Mapping[Any, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_fields.items():
        normalized[_decode_redis_value(key)] = _decode_redis_value(value)
    return normalized


def _to_deadletter_payload(
    *,
    reason: SyncStreamFailureReason,
    message_id: str | None,
    fields: Mapping[str, Any],
    error_message: str | None,
) -> dict[str, str]:
    payload = {
        "reason": reason.value,
        "event_id": str(fields.get("event_id") or ""),
        "job_id": str(fields.get("job_id") or ""),
        "connector": str(fields.get("connector") or ""),
        "sync_type": str(fields.get("sync_type") or ""),
        "scope_id": str(fields.get("scope_id") or ""),
        "target_type": str(fields.get("target_type") or ""),
        "target_id": str(fields.get("target_id") or ""),
        "source_stream": SYNC_EVENTS_STREAM_KEY,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    if message_id:
        payload["source_message_id"] = message_id
    if error_message:
        payload["error"] = error_message
    return payload


async def ensure_consumer_group() -> None:
    redis = await get_redis_client()
    try:
        await redis.xgroup_create(
            name=SYNC_EVENTS_STREAM_KEY,
            groupname=SYNC_EVENTS_CONSUMER_GROUP,
            id=STREAM_CLAIM_START_ID,
            mkstream=True,
        )
        logger.info(
            "[SYNC][STREAM][QUEUE] Consumer group created: stream=%s, group=%s",
            SYNC_EVENTS_STREAM_KEY,
            SYNC_EVENTS_CONSUMER_GROUP,
        )
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            logger.debug(
                "[SYNC][STREAM][QUEUE] Consumer group already exists: stream=%s, group=%s",
                SYNC_EVENTS_STREAM_KEY,
                SYNC_EVENTS_CONSUMER_GROUP,
            )
            return
        raise


async def publish_task(task: SyncStreamTask) -> str:
    redis = await get_redis_client()
    message_id = await redis.xadd(SYNC_EVENTS_STREAM_KEY, task.to_stream_fields())
    return _decode_redis_value(message_id)


async def publish_tasks(tasks: list[SyncStreamTask]) -> PublishTasksResult:
    if not tasks:
        return PublishTasksResult(
            requested_count=0,
            published_count=0,
            message_ids=[],
            partial_success=False,
        )

    message_ids: list[str] = []

    for index, task in enumerate(tasks):
        try:
            message_ids.append(await publish_task(task))
        except Exception as exc:
            return PublishTasksResult(
                requested_count=len(tasks),
                published_count=len(message_ids),
                message_ids=message_ids,
                partial_success=len(message_ids) > 0,
                error_message=str(exc),
                failed_at_index=index,
                failed_event_id=task.event_id,
            )

    return PublishTasksResult(
        requested_count=len(tasks),
        published_count=len(message_ids),
        message_ids=message_ids,
        partial_success=False,
    )


async def ack_message(message_id: str) -> AckDeleteResult:
    return await ack_messages([message_id])


async def ack_messages(message_ids: list[str]) -> AckDeleteResult:
    if not message_ids:
        return AckDeleteResult(acked=0, deleted=0)

    redis = await get_redis_client()
    acked = int(
        await redis.xack(
            SYNC_EVENTS_STREAM_KEY,
            SYNC_EVENTS_CONSUMER_GROUP,
            *message_ids,
        )
    )
    deleted = int(
        await redis.xdel(
            SYNC_EVENTS_STREAM_KEY,
            *message_ids,
        )
    )
    return AckDeleteResult(acked=acked, deleted=deleted)


async def delete_messages(message_ids: list[str]) -> int:
    if not message_ids:
        return 0

    redis = await get_redis_client()
    deleted = await redis.xdel(
        SYNC_EVENTS_STREAM_KEY,
        *message_ids,
    )
    return int(deleted)


async def publish_deadletter(
    *,
    reason: SyncStreamFailureReason,
    message_id: str | None,
    fields: Mapping[str, Any],
    error_message: str | None = None,
) -> str:
    redis = await get_redis_client()
    payload = _to_deadletter_payload(
        reason=reason,
        message_id=message_id,
        fields=fields,
        error_message=error_message,
    )
    deadletter_id = await redis.xadd(SYNC_EVENTS_DEADLETTER_STREAM_KEY, payload)
    return _decode_redis_value(deadletter_id)


async def _parse_messages_with_deadletter(
    raw_entries: list[tuple[Any, Mapping[Any, Any]]],
) -> list[SyncStreamMessage]:
    parsed_messages: list[SyncStreamMessage] = []

    for raw_message_id, raw_fields in raw_entries:
        message_id = _decode_redis_value(raw_message_id)
        normalized_fields = _normalize_stream_fields(raw_fields)

        try:
            task = SyncStreamTask.from_stream_fields(normalized_fields)
            parsed_messages.append(
                SyncStreamMessage(
                    message_id=message_id,
                    task=task,
                )
            )
        except Exception as exc:
            await publish_deadletter(
                reason=SyncStreamFailureReason.INVALID_STREAM_PAYLOAD,
                message_id=message_id,
                fields=normalized_fields,
                error_message=str(exc),
            )
            ack_result = await ack_message(message_id)
            logger.error(
                (
                    "[SYNC][STREAM][QUEUE] Invalid payload moved to deadletter: "
                    "message_id=%s, acked=%s, deleted=%s, error=%s"
                ),
                message_id,
                ack_result.acked,
                ack_result.deleted,
                exc,
            )
    return parsed_messages


async def read_new_messages(
    *,
    consumer_name: str,
    count: int = 10,
    block_ms: int | None = None,
) -> list[SyncStreamMessage]:
    redis = await get_stream_redis_client()

    block_timeout_ms = (
        settings.SYNC_QUEUE_BLOCK_TIMEOUT_SECONDS * 1000
        if block_ms is None
        else max(0, block_ms)
    )

    xreadgroup_kwargs = {
        "groupname": SYNC_EVENTS_CONSUMER_GROUP,
        "consumername": consumer_name,
        "streams": {SYNC_EVENTS_STREAM_KEY: STREAM_READ_NEW_MESSAGE_ID},
        "count": max(1, count),
    }
    if block_timeout_ms > 0:
        xreadgroup_kwargs["block"] = block_timeout_ms

    try:
        raw = await redis.xreadgroup(**xreadgroup_kwargs)
    except (RedisTimeoutError, RedisConnectionError):
        await reset_stream_redis_client(redis)
        raise

    if not raw:
        return []

    entries: list[tuple[Any, Mapping[Any, Any]]] = []
    for _, stream_entries in raw:
        entries.extend(stream_entries)

    return await _parse_messages_with_deadletter(entries)


async def autoclaim_stale_messages(
    *,
    consumer_name: str,
    min_idle_ms: int,
    start_id: str = STREAM_CLAIM_START_ID,
    count: int = 100,
) -> SyncClaimBatch:
    redis = await get_stream_redis_client()

    try:
        raw = await redis.xautoclaim(
            name=SYNC_EVENTS_STREAM_KEY,
            groupname=SYNC_EVENTS_CONSUMER_GROUP,
            consumername=consumer_name,
            min_idle_time=max(1, min_idle_ms),
            start_id=start_id,
            count=max(1, count),
        )
    except (RedisTimeoutError, RedisConnectionError):
        await reset_stream_redis_client(redis)
        raise

    if not raw:
        return SyncClaimBatch(next_start_id=start_id, messages=[])

    next_start_id = _decode_redis_value(raw[0])
    raw_entries = raw[1] if len(raw) > 1 else []
    messages = await _parse_messages_with_deadletter(raw_entries)
    return SyncClaimBatch(next_start_id=next_start_id, messages=messages)
