from __future__ import annotations

import logging
from typing import Iterable

from catchup.sync.common.exceptions import (
    RedisStreamInitializationError,
    RedisStreamPublishError,
)
from catchup.sync.stream_runtime.stream_constants import STREAM_CLAIM_START_ID
from catchup.sync.stream_runtime.stream_queue import (
    ack_messages,
    autoclaim_stale_messages,
    ensure_consumer_group,
    publish_tasks,
    read_new_messages,
)
from catchup.sync.stream_runtime.stream_schemas import (
    PublishTasksResult,
    SyncStreamMessage,
    SyncStreamTask,
)

logger = logging.getLogger(__name__)


def build_stream_tasks(
    *,
    job_id: str,
    event_ids: Iterable[str],
    connector: str,
    sync_type: str,
    scope_id: str,
    target_type: str,
    target_ids: list[str] | None = None,
    max_attempts: int = 3,
) -> list[SyncStreamTask]:
    tasks: list[SyncStreamTask] = []
    target_ids = target_ids or []

    for index, event_id in enumerate(event_ids):
        normalized_event_id = event_id.strip()
        if not normalized_event_id:
            continue

        target_id = (
            target_ids[index]
            if index < len(target_ids) and target_ids[index]
            else normalized_event_id
        )
        tasks.append(
            SyncStreamTask(
                event_id=normalized_event_id,
                job_id=job_id,
                connector=connector,
                sync_type=sync_type,
                scope_id=scope_id,
                target_type=target_type,
                target_id=target_id,
                attempt=0,
                max_attempts=max_attempts,
            )
        )

    return tasks


async def initialize_stream_runtime() -> None:
    await ensure_consumer_group()


async def publish_job_events(
    *,
    job_id: str,
    event_ids: list[str],
    connector: str,
    sync_type: str,
    scope_id: str,
    target_type: str,
    target_ids: list[str] | None = None,
    max_attempts: int = 3,
) -> PublishTasksResult:
    tasks = build_stream_tasks(
        job_id=job_id,
        event_ids=event_ids,
        connector=connector,
        sync_type=sync_type,
        scope_id=scope_id,
        target_type=target_type,
        target_ids=target_ids,
        max_attempts=max_attempts,
    )
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
        raise RedisStreamInitializationError(
            metadata={
                "requested_count": len(tasks),
                "job_id": job_id,
                "scope_id": scope_id,
                "error_message": str(exc),
            },
        ) from exc

    try:
        publish_result = await publish_tasks(tasks)
    except Exception as exc:
        raise RedisStreamPublishError(
            metadata={
                "requested_count": len(tasks),
                "job_id": job_id,
                "scope_id": scope_id,
                "error_message": str(exc),
            },
        ) from exc

    logger.info(
        "[SYNC][STREAM][RUNTIME] Published tasks: connector=%s, sync_type=%s, scope_id=%s, job_id=%s, event_count=%s, published_count=%s, partial_success=%s",
        connector,
        sync_type,
        scope_id,
        job_id,
        len(tasks),
        publish_result.published_count,
        publish_result.partial_success,
    )
    if publish_result.published_count != publish_result.requested_count:
        raise RedisStreamPublishError(
            metadata={
                "requested_count": publish_result.requested_count,
                "published_count": publish_result.published_count,
                "partial_success": publish_result.partial_success,
                "failed_at_index": publish_result.failed_at_index,
                "failed_event_id": publish_result.failed_event_id,
                "error_message": publish_result.error_message,
                "job_id": job_id,
                "scope_id": scope_id,
            },
        )
    return publish_result


async def read_ready_messages(
    *,
    consumer_name: str,
    reclaim_min_idle_ms: int,
    reclaim_start_id: str = STREAM_CLAIM_START_ID,
    reclaim_count: int = 100,
    read_count: int = 50,
    block_ms: int | None = None,
) -> tuple[list[SyncStreamMessage], str]:
    claim_batch = await autoclaim_stale_messages(
        consumer_name=consumer_name,
        min_idle_ms=reclaim_min_idle_ms,
        start_id=reclaim_start_id,
        count=reclaim_count,
    )
    new_messages = await read_new_messages(
        consumer_name=consumer_name,
        count=read_count,
        block_ms=block_ms,
    )

    if not claim_batch.messages:
        return new_messages, claim_batch.next_start_id
    if not new_messages:
        return claim_batch.messages, claim_batch.next_start_id

    merged_by_message_id: dict[str, SyncStreamMessage] = {}
    for message in claim_batch.messages:
        merged_by_message_id[message.message_id] = message
    for message in new_messages:
        merged_by_message_id[message.message_id] = message

    merged_messages = list(merged_by_message_id.values())
    return merged_messages, claim_batch.next_start_id


async def ack_consumed_messages(messages: list[SyncStreamMessage]) -> int:
    message_ids = [message.message_id for message in messages]
    return await ack_messages(message_ids)
