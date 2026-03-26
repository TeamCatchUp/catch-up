from __future__ import annotations

import asyncio
import logging

from catchup.configs.config import settings
from catchup.db.models import SyncType
from catchup.sync.common.protocols import WorkerProtocol
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.full_retry import publish_retry_ready_full_sync_events
from catchup.sync.stream_runtime.stream_constants import STREAM_CLAIM_START_ID
from catchup.sync.stream_runtime.sync_runtime import ack_consumed_messages
from catchup.sync.stream_runtime.sync_runtime import initialize_stream_runtime
from catchup.sync.stream_runtime.sync_runtime import read_ready_messages
from catchup.worker.common import consumer_name
from catchup.worker.common import task_lock_key
from catchup.worker.full_sync_processor import process_full_sync_message
from catchup.worker.incremental_processor import process_incremental_message

logger = logging.getLogger(__name__)


async def _publish_retry_ready_full_sync_events() -> None:
    result = await publish_retry_ready_full_sync_events(
        limit=max(1, settings.SYNC_WORKER_CHANNEL_CONCURRENCY * 10),
    )
    if result["published"] == 0 and result["errors"] == 0:
        return

    logger.info("[FULL][RETRY] Runtime publish cycle completed: result=%s", result)


# Sync Type에 따라서 분기
async def _process_message(
    message: SyncStreamMessage,
    service_cache: dict[str, object],
    *,
    lease_owner: str,
) -> None:
    try:
        if message.task.sync_type == SyncType.INCREMENTAL:
            await process_incremental_message(
                message,
                service_cache,
                lease_owner=lease_owner,
            )
            return

        await process_full_sync_message(
            message,
            service_cache,
        )
    finally:
        try:
            await ack_consumed_messages([message])
        except Exception:
            logger.exception(
                "[SYNC][WORKER] Message ack failed: message_id=%s",
                message.message_id,
            )


class SyncWorker(WorkerProtocol):
    def __init__(self) -> None:
        self._service_cache: dict[str, object] = {}
        self._target_locks: dict[tuple[str, str, str, str], asyncio.Lock] = {}
        self._parallelism = max(1, int(settings.SYNC_WORKER_CHANNEL_CONCURRENCY))
        self._semaphore = asyncio.Semaphore(self._parallelism)
        self._consumer = ""

    async def process(self, message: SyncStreamMessage) -> None:
        lock_key = task_lock_key(message.task)
        lock = self._target_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            async with self._semaphore:
                await _process_message(
                    message,
                    self._service_cache,
                    lease_owner=self._consumer,
                )

    # Worker 메인 루프
    async def run_forever(self, stop_event: asyncio.Event) -> None:
        consumer = consumer_name()
        reclaim_start_id = STREAM_CLAIM_START_ID
        self._service_cache = {}
        self._consumer = consumer
        self._target_locks = {}
        self._parallelism = max(1, int(settings.SYNC_WORKER_CHANNEL_CONCURRENCY))
        self._semaphore = asyncio.Semaphore(self._parallelism)

        await initialize_stream_runtime()
        logger.info("[SYNC][WORKER] Worker started: consumer=%s", consumer)

        while not stop_event.is_set():
            try:
                await _publish_retry_ready_full_sync_events()

                messages, reclaim_start_id = await read_ready_messages(
                    consumer_name=consumer,
                    reclaim_min_idle_ms=max(
                        1, int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS * 1000)
                    ),
                    reclaim_start_id=reclaim_start_id,
                    reclaim_count=max(
                        1, settings.SYNC_WORKER_CHANNEL_CONCURRENCY * 10
                    ),
                    read_count=max(1, settings.SYNC_WORKER_CHANNEL_CONCURRENCY),
                    block_ms=max(0, settings.SYNC_QUEUE_BLOCK_TIMEOUT_SECONDS * 1000),
                )

                if not messages:
                    await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)
                    continue

                tasks = [
                    asyncio.create_task(self.process(message))
                    for message in messages
                    if not stop_event.is_set()
                ]
                if not tasks:
                    continue

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.exception(
                            "[SYNC][WORKER] Worker task failed",
                            exc_info=result,
                        )
            except Exception:
                logger.exception("[SYNC][WORKER] Worker loop error")
                await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)

        logger.info("[SYNC][WORKER] Worker stopped: consumer=%s", consumer)


_sync_worker = SyncWorker()


# 모듈 외부에서 worker 루프를 시작할 때 사용하는 진입점이다.
async def run_forever(stop_event: asyncio.Event) -> None:
    await _sync_worker.run_forever(stop_event)
