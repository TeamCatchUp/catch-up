from __future__ import annotations

import asyncio
import logging

from collections import deque
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
        self._consumer = ""
        self._inflight: dict[asyncio.Task[None], tuple[str, str, str, str]] = {}
        self._busy_keys: set[tuple[str, str, str, str]] = set()
        self._pending: deque[SyncStreamMessage] = deque()

    async def process(self, message: SyncStreamMessage) -> None:
        """Target에 대한 Lock Key 획득, _process_message() 호출"""
        lock_key = task_lock_key(message.task)
        lock = self._target_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            await _process_message(
                message,
                self._service_cache,
                lease_owner=self._consumer,
            )

    def _reset_runtime_state(self, consumer: str) -> None:
        self._service_cache = {}
        self._consumer = consumer
        self._target_locks = {}
        self._parallelism = max(1, int(settings.SYNC_WORKER_CHANNEL_CONCURRENCY))
        self._inflight = {}
        self._busy_keys = set()
        self._pending = deque()

    def _start_message_task(self, message: SyncStreamMessage) -> None:
        """message의 lock_key를 _inflight에 저장, AsyncTask 생성"""
        lock_key = task_lock_key(message.task)
        self._busy_keys.add(lock_key)

        task = asyncio.create_task(self.process(message))
        self._inflight[task] = lock_key

    def _schedule_pending_messages(self) -> None:
        """pending 큐에 쌓여 있는 event 중 실행가능한 것을 inflight으로 이동"""
        if not self._pending:
            return

        pending_count = len(self._pending)
        for _ in range(pending_count):
            if len(self._inflight) >= self._parallelism:
                return

            message = self._pending.popleft()
            lock_key = task_lock_key(message.task)

            if lock_key in self._busy_keys:
                self._pending.append(message)
                continue

            self._start_message_task(message)

    async def _reap_completed_tasks(self) -> None:
        """완료된 Task를 회수하고, 예외처리"""
        done_tasks = [task for task in self._inflight if task.done()]
        for task in done_tasks:
            lock_key = self._inflight.pop(task)
            self._busy_keys.discard(lock_key)

            try:
                task.result()
            except Exception:
                logger.exception("[SYNC][WORKER] Worker task failed")

    async def _wait_for_next_completion(self) -> None:
        """실행 중 task 중 하나라도 끝날때까지 기다림"""
        if not self._inflight:
            return

        await asyncio.wait(
            set(self._inflight.keys()),
            return_when=asyncio.FIRST_COMPLETED,
        )

    def _read_capacity(self) -> int:
        """현재 시점에 수용 가능한 event 개수를 계산"""
        available_workers = max(0, self._parallelism - len(self._inflight))
        pending_buffer_room = max(0, self._parallelism - len(self._pending))
        return min(available_workers, pending_buffer_room)

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        consumer = consumer_name()
        reclaim_start_id = STREAM_CLAIM_START_ID
        self._reset_runtime_state(consumer)

        await initialize_stream_runtime()
        logger.info(
            "[SYNC][WORKER] Worker started: consumer=%s, parallelism=%s",
            consumer,
            self._parallelism,
        )

        while True:
            try:
                # completed event 회수
                await self._reap_completed_tasks()

                # pending queue에서 지금 실행 가능한 메세지를 pending 슬롯으로 옮김
                self._schedule_pending_messages()

                # stop 요청 도착, 남은 이벤트가 없으면 메인 루프 종료
                if stop_event.is_set() and not self._pending and not self._inflight:
                    break
                
                # stop 요청이 온 뒤에는 새 메시지를 읽지 않고 현재 작업 drain
                if stop_event.is_set():
                    if self._inflight:
                        await self._wait_for_next_completion()
                    else:
                        await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)
                    continue
                
                # retry 대기 상태인 이벤트를 다시 stream에 publish
                await _publish_retry_ready_full_sync_events()

                # 추가 실행 가능한 event 수를 계산
                read_count = self._read_capacity()
                
                # 빈 자리가 없으면 새 event를 읽지 않고, 기존 작업 중 하나가 끝나기를 기다림
                if read_count <= 0:
                    if self._inflight:
                        await self._wait_for_next_completion()
                    else:
                        await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)
                    continue
                
                # 
                block_ms = (
                    max(0, settings.SYNC_QUEUE_BLOCK_TIMEOUT_SECONDS * 1000)
                    if not self._inflight and not self._pending
                    else 0
                )

                # stale message reclaim 결과를 새 event와 함께 읽음
                messages, reclaim_start_id = await read_ready_messages(
                    consumer_name=consumer,
                    reclaim_min_idle_ms=max(
                        1,
                        int(settings.SYNC_LOCK_CHANNEL_TTL_SECONDS * 1000),
                    ),
                    reclaim_start_id=reclaim_start_id,
                    reclaim_count=max(
                        1,
                        settings.SYNC_WORKER_CHANNEL_CONCURRENCY * 10,
                    ),
                    read_count=read_count,
                    block_ms=block_ms,
                )

                # 읽은 event가 없으면 대기
                if not messages:
                    if self._inflight:
                        await self._wait_for_next_completion()
                    else:
                        await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)
                    continue
                
                # 읽어온 메세지를 pending 큐에 넣고 즉시 실행 가능한 것부터 다시 배치
                self._pending.extend(messages)
                self._schedule_pending_messages()
            except Exception:
                # 루프 자체의 에러는 로그만 남기고 sleep후 재시도
                logger.exception("[SYNC][WORKER] Worker loop error")
                await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)

        # 메인 루프 종료 후 남아있는 inflight/pending event를 정리
        while self._inflight or self._pending:
            try:
                # 실행가능한 pending event가 있으면 슬롯에 올린다
                self._schedule_pending_messages()

                # 실행 중인 task가 있다면 끝날 때까지 기다리고 회수한다.
                if self._inflight:
                    await self._wait_for_next_completion()
                    await self._reap_completed_tasks()
                    continue
                
                # inflight는 없는데 pending만 남아있으면 비정상 상태 -> 경고 후 종료
                if self._pending:
                    logger.warning(
                        "[SYNC][WORKER] Pending messages left without inflight tasks: pending=%s",
                        len(self._pending),
                    )
                    break
            except Exception:
                logger.exception("[SYNC][WORKER] Worker shutdown drain error")
                break

        logger.info("[SYNC][WORKER] Worker stopped: consumer=%s", consumer)


_sync_worker = SyncWorker()


async def run_forever(stop_event: asyncio.Event) -> None:
    await _sync_worker.run_forever(stop_event)
