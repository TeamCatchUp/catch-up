from __future__ import annotations

import random
from datetime import datetime, timezone

from catchup.configs.config import settings
from catchup.connectors.slack.sync_runtime.constants import (
    SLACK_FULL_SYNC_DEADLETTER_KEY,
    SLACK_FULL_SYNC_DELAYED_KEY,
    SLACK_FULL_SYNC_PROCESSING_KEY,
    SLACK_FULL_SYNC_QUEUE_KEY,
)
from catchup.connectors.slack.sync_runtime.schemas import (
    DelayedQueueItem,
    SlackChannelSyncTask,
)
from catchup.utils.redis import get_redis_client

def _now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def _calc_backoff_seconds(attempt: int) -> float:
    """
    기본 지수 백오프 + jitter
    """
    base = settings.SYNC_JOB_RETRY_BASE_DELAY_SECONDS
    max_delay = settings.SYNC_JOB_RETRY_MAX_DELAY_SECONDS

    # attempt=1 -> base, attempt=2 -> base*2 ...
    delay = min(base * (2 ** max(0, attempt - 1)), max_delay)
    jitter = random.uniform(0, max(0.3, delay * 0.1))
    return delay + jitter


async def enqueue_task(task: SlackChannelSyncTask) -> None:
    redis = await get_redis_client()
    await redis.rpush(SLACK_FULL_SYNC_QUEUE_KEY, task.to_queue_payload())

async def enqueue_tasks(tasks: list[SlackChannelSyncTask]) -> None:
    if not tasks:
        return
    
    redis = await get_redis_client()
    payloads = [task.to_queue_payload() for task in tasks]
    await redis.rpush(SLACK_FULL_SYNC_QUEUE_KEY, *payloads)

async def claim_task(block_timeout_seconds:int | None = None) -> SlackChannelSyncTask | None:

    redis = await get_redis_client()
    timeout_seconds = (
        settings.SYNC_QUEUE_BLOCK_TIMEOUT_SECONDS
        if block_timeout_seconds is None
        else block_timeout_seconds
    )

    raw = await redis.brpoplpush(
        SLACK_FULL_SYNC_QUEUE_KEY,
        SLACK_FULL_SYNC_PROCESSING_KEY,
        timeout=timeout_seconds,
    )
    if raw is None:
        return None
    
    payload = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    return SlackChannelSyncTask.from_queue_payload(payload)

async def ack_task(task: SlackChannelSyncTask) -> int:
    redis = await get_redis_client()
    removed = await redis.lrem(
        SLACK_FULL_SYNC_PROCESSING_KEY,
        1,
        task.to_queue_payload(),
    )
    return int(removed)

async def move_processing_back_to_queue() -> int:
    """
    processing 큐에 남아 있던 이벤트를 메인 큐로 복구
    """
    redis = await get_redis_client()
    moved = 0

    while True:
        raw = await redis.rpoplpush(
            SLACK_FULL_SYNC_PROCESSING_KEY,
            SLACK_FULL_SYNC_QUEUE_KEY,
        )
        if raw is None:
            break
        moved += 1

    return moved

async def enqueue_delayed(task: SlackChannelSyncTask, attempt: int) -> float:
    """
    채널 락 충돌/재시도용 delayed 큐 적재
    """
    redis = await get_redis_client()
    delay_seconds = _calc_backoff_seconds(attempt)
    due_at_epoch_ms = _now_epoch_ms() + int(delay_seconds * 1000)

    item = DelayedQueueItem(
        due_at_epoch_ms=due_at_epoch_ms,
        task=task,
    )
    await redis.zadd(
        SLACK_FULL_SYNC_DELAYED_KEY,
        {item.to_queue_payload(): float(due_at_epoch_ms)},
    )
    return delay_seconds

async def flush_due_delayed_to_queue(limit: int = 200) -> int:
    """
    due 시각이 지난 delayed 이벤트를 메인 큐로 이동
    """
    redis = await get_redis_client()
    now_ms = _now_epoch_ms()

    raw_items = await redis.zrangebyscore(
        SLACK_FULL_SYNC_DELAYED_KEY,
        min=0,
        max=now_ms,
        start=0,
        num=limit,
    )
    if not raw_items:
        return 0

    moved = 0
    for raw in raw_items:
        payload = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

        # 제거 성공 시에만 큐로 이동(중복 이동 방지)
        removed = await redis.zrem(SLACK_FULL_SYNC_DELAYED_KEY, payload)
        if int(removed) != 1:
            continue

        item = DelayedQueueItem.from_queue_payload(payload)
        await enqueue_task(item.task)
        moved += 1

    return moved

async def move_to_deadletter(task: SlackChannelSyncTask) -> None:
    redis = await get_redis_client()
    await redis.rpush(SLACK_FULL_SYNC_DEADLETTER_KEY, task.to_queue_payload())
