from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
import logging

from catchup.configs.config import settings
from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.connectors.slack.sync_runtime import job_store
from catchup.connectors.slack.sync_runtime import queue as runtime_queue
from catchup.connectors.slack.sync_runtime import events as runtime_events
from catchup.connectors.slack.sync_runtime import locks as runtime_locks
from catchup.connectors.slack.sync_runtime.audit import (
    emit_channel_completed,
    emit_channel_failed,
    emit_channel_requeued,
    emit_channel_started,
    emit_job_completed,
    emit_job_failed,
    emit_job_started,
)
from catchup.connectors.slack.sync_runtime.constants import (
    SyncEventType,
    SyncFailureReason,
    SyncJobStatus,
)
from catchup.connectors.slack.sync_runtime.schemas import SlackChannelSyncTask
from catchup.db.engine import SessionLocal

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    processing_incremented: bool = False
    acked: bool = False
    channel_locked: bool = False



def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    
def _calc_duration_ms(started_at: str | None, ended_at: str | None) -> int | None:
    started = _parse_iso(started_at)
    ended = _parse_iso(ended_at)
    if started is None or ended is None:
        return None
    return int((ended - started).total_seconds() * 1000)

async def _ack_safely(task: SlackChannelSyncTask) -> None:
    try:
        await runtime_queue.ack_task(task)
    except Exception:
        logger.exception("[SLACK][FULL SYNC][WORKER] Failed to ack task: event_id=%s", task.event_id)




async def _ensure_job_started(job_id: str, team_id: str, total_channels: int) -> None:
    started = await job_store.mark_job_started_if_accepted(job_id)
    if not started:
        return

    await runtime_events.append_event(
        job_id=job_id,
        team_id=team_id,
        event_type=SyncEventType.JOB_STARTED,
        payload={"total_channels": total_channels},
    )
    emit_job_started(
        job_id=job_id,
        team_id=team_id,
        total_channels=total_channels,
    )

async def _finalize_job_if_done(job_id: str, team_id: str) -> None:
    meta = await job_store.get_job(job_id)
    if meta is None:
        return

    if meta.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
        return

    done_channels = meta.completed_channels + meta.failed_channels
    if meta.total_channels <= 0 or done_channels < meta.total_channels:
        return

    await job_store.mark_job_completed(
        job_id=job_id,
        failed_channels=meta.failed_channels,
        last_error=meta.last_error,
    )

    finalized = await job_store.get_job(job_id)
    if finalized is None:
        return

    duration_ms = _calc_duration_ms(finalized.started_at, finalized.completed_at)

    if finalized.status == SyncJobStatus.SUCCESS:
        await runtime_events.append_event(
            job_id=job_id,
            team_id=team_id,
            event_type=SyncEventType.JOB_COMPLETED,
            payload={
                "total_channels": finalized.total_channels,
                "completed_channels": finalized.completed_channels,
                "failed_channels": finalized.failed_channels,
                "requeued_channels": finalized.requeued_channels,
                "synced_messages": finalized.synced_messages,
            },
        )
        emit_job_completed(
            job_id=job_id,
            team_id=team_id,
            total_channels=finalized.total_channels,
            completed_channels=finalized.completed_channels,
            failed_channels=finalized.failed_channels,
            requeued_channels=finalized.requeued_channels,
            total_synced_messages=finalized.synced_messages,
            duration_ms=duration_ms,
        )
    else:
        await runtime_events.append_event(
            job_id=job_id,
            team_id=team_id,
            event_type=SyncEventType.JOB_FAILED,
            payload={
                "total_channels": finalized.total_channels,
                "completed_channels": finalized.completed_channels,
                "failed_channels": finalized.failed_channels,
                "last_error": finalized.last_error,
            },
        )
        emit_job_failed(
            job_id=job_id,
            team_id=team_id,
            failure_reason=SyncFailureReason.UNEXPECTED_ERROR.value,
            error_summary=finalized.last_error,
            duration_ms=duration_ms,
        )

    await runtime_locks.release_all_channel_locks_for_job(team_id, job_id)
    await runtime_locks.release_team_lock_if_owner(team_id, job_id)


async def _precheck_job(task: SlackChannelSyncTask) -> tuple[bool, str | None, int]:
    meta = await job_store.get_job(task.job_id)
    if meta is None:
        await _ack_safely(task)
        return False, None, 0
    
    if meta.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
        await _ack_safely(task)
        return False, meta.team_id, meta.total_channels
    
    team_owner = await runtime_locks.get_team_lock_owner(task.team_id)
    if team_owner != task.job_id:
        await _ack_safely(task)
        return False, meta.team_id, meta.total_channels

    await _ensure_job_started(task.job_id, task.team_id, meta.total_channels)
    return True, meta.team_id, meta.total_channels

async def _start_processing(task: SlackChannelSyncTask, ctx: TaskContext) -> None:
    await job_store.increment_field(task.job_id, "processing_channels", 1)
    ctx.processing_incremented = True

    ctx.channel_locked = await runtime_locks.acquire_channel_lock(
        task.team_id,
        task.channel_id,
        task.job_id,
    )

async def _handle_lock_conflict(task: SlackChannelSyncTask, ctx: TaskContext) -> None:
    await _ack_safely(task)
    ctx.acked = True

    delay = await runtime_queue.enqueue_delayed(task, attempt=task.attempt)
    await job_store.increment_field(task.job_id, "requeued_channels", 1)

    await runtime_events.append_event(
        job_id=task.job_id,
        team_id=task.team_id,
        event_type=SyncEventType.CHANNEL_REQUEUED,
        payload={
            "channel_id": task.channel_id,
            "channel_name": task.channel_name,
            "attempt": task.attempt,
            "reason": SyncFailureReason.CHANNEL_LOCK_CONFLICT.value,
            "delay_seconds": delay,
        },
    )
    emit_channel_requeued(
        job_id=task.job_id,
        team_id=task.team_id,
        channel_id=task.channel_id,
        channel_name=task.channel_name,
        attempt=task.attempt,
        delay_seconds=delay,
    )

async def _lock_refresh_loop(
    task: SlackChannelSyncTask,
    sync_task: asyncio.Task[dict],
    lock_lost_event: asyncio.Event,
) -> None:
    interval = max(
        1.0,
        min(
            settings.SYNC_LOCK_REFRESH_INTERVAL_SECONDS,
            settings.SYNC_LOCK_CHANNEL_TTL_SECONDS / 2,
        ),
    )

    while not sync_task.done():
        await asyncio.sleep(interval)
        if sync_task.done():
            return

        try:
            team_lock_ok = await runtime_locks.refresh_team_lock_if_owner(
                task.team_id,
                task.job_id,
            )
            channel_lock_ok = await runtime_locks.refresh_channel_lock_if_owner(
                task.team_id,
                task.channel_id,
                task.job_id,
            )
        except Exception:
            logger.exception(
                "[SLACK][FULL SYNC][WORKER] Lock refresh error: job_id=%s, channel_id=%s",
                task.job_id,
                task.channel_id,
            )
            team_lock_ok = False
            channel_lock_ok = False

        if team_lock_ok and channel_lock_ok:
            continue

        logger.error(
            "[SLACK][FULL SYNC][WORKER] Lock ownership lost: job_id=%s, channel_id=%s, team_lock_ok=%s, channel_lock_ok=%s",
            task.job_id,
            task.channel_id,
            team_lock_ok,
            channel_lock_ok,
        )
        lock_lost_event.set()
        return

async def _get_or_create_service(
    team_id: str,
    service_cache: dict,
):
    # worker loop 단위로 팀 서비스 인스턴스를 재사용하여 초기화 오버헤드를 줄입니다.
    cached = service_cache.get(team_id)
    if cached is not None:
        return cached

    with SessionLocal() as db:
        service = await create_slack_ingestion_service(db, team_id)
    service_cache[team_id] = service
    return service


async def _execute_channel_sync(task: SlackChannelSyncTask, service_cache: dict) -> dict:
    await runtime_events.append_event(
        job_id=task.job_id,
        team_id=task.team_id,
        event_type=SyncEventType.CHANNEL_STARTED,
        payload={
            "channel_id": task.channel_id,
            "channel_name": task.channel_name,
            "attempt": task.attempt,
        },
    )
    emit_channel_started(
        job_id=task.job_id,
        team_id=task.team_id,
        channel_id=task.channel_id,
        channel_name=task.channel_name,
        attempt=task.attempt,
    )

    service = await _get_or_create_service(task.team_id, service_cache)

    with SessionLocal() as db:
        sync_task = asyncio.create_task(
            service.sync_channel_messages(
                channel_id=task.channel_id,
                channel_name=task.channel_name,
                sync_from=task.sync_from,
                db=db,
                skip_delete=True,
            )
        )
        lock_lost_event = asyncio.Event()
        lock_refresh_task = asyncio.create_task(
            _lock_refresh_loop(task, sync_task, lock_lost_event)
        )

        try:
            result = await sync_task
            if lock_lost_event.is_set():
                raise RuntimeError("lock ownership lost during channel sync")
            return result
        except asyncio.CancelledError as exc:
            if lock_lost_event.is_set():
                raise RuntimeError("lock ownership lost during channel sync") from exc
            raise
        finally:
            lock_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await lock_refresh_task

async def _handle_sync_success(task: SlackChannelSyncTask, result: dict, ctx: TaskContext) -> None:
    await _ack_safely(task)
    ctx.acked = True

    await job_store.increment_field(task.job_id, "completed_channels", 1)

    synced = int(result.get("synced", 0))
    errors = int(result.get("errors", 0))
    skipped = bool(result.get("skipped", False))

    if synced > 0:
        await job_store.increment_field(task.job_id, "synced_messages", synced)

    await runtime_events.append_event(
        job_id=task.job_id,
        team_id=task.team_id,
        event_type=SyncEventType.CHANNEL_COMPLETED,
        payload={
            "channel_id": task.channel_id,
            "channel_name": task.channel_name,
            "synced": synced,
            "errors": errors,
            "skipped": skipped,
        },
    )
    emit_channel_completed(
        job_id=task.job_id,
        team_id=task.team_id,
        channel_id=task.channel_id,
        channel_name=task.channel_name,
        synced_count=synced,
        error_count=errors,
        skipped=skipped,
    )


async def _handle_sync_failure(task: SlackChannelSyncTask, exc: Exception, ctx: TaskContext) -> None:
    await _ack_safely(task)
    ctx.acked = True

    next_attempt = task.attempt + 1
    error_summary = str(exc)

    if next_attempt >= task.max_attempts:
        await runtime_queue.move_to_deadletter(task)
        await job_store.increment_field(task.job_id, "failed_channels", 1)
        await job_store.set_last_error(task.job_id, error_summary)

        await runtime_events.append_event(
            job_id=task.job_id,
            team_id=task.team_id,
            event_type=SyncEventType.CHANNEL_FAILED,
            payload={
                "channel_id": task.channel_id,
                "channel_name": task.channel_name,
                "attempt": next_attempt,
                "reason": SyncFailureReason.MAX_RETRIES_EXCEEDED.value,
                "error": error_summary,
            },
        )
        emit_channel_failed(
            job_id=task.job_id,
            team_id=task.team_id,
            channel_id=task.channel_id,
            channel_name=task.channel_name,
            failure_reason=SyncFailureReason.MAX_RETRIES_EXCEEDED.value,
            error_summary=error_summary,
            attempt=next_attempt,
            retryable=False,
        )
        return

    retry_task = task.model_copy(update={"attempt": next_attempt})
    delay = await runtime_queue.enqueue_delayed(retry_task, attempt=next_attempt)
    await job_store.increment_field(task.job_id, "requeued_channels", 1)

    await runtime_events.append_event(
        job_id=task.job_id,
        team_id=task.team_id,
        event_type=SyncEventType.CHANNEL_REQUEUED,
        payload={
            "channel_id": task.channel_id,
            "channel_name": task.channel_name,
            "attempt": next_attempt,
            "reason": SyncFailureReason.SLACK_SYNC_EXCEPTION.value,
            "error": error_summary,
            "delay_seconds": delay,
        },
    )
    emit_channel_requeued(
        job_id=task.job_id,
        team_id=task.team_id,
        channel_id=task.channel_id,
        channel_name=task.channel_name,
        attempt=next_attempt,
        delay_seconds=delay,
    )


async def _finalize_task(task: SlackChannelSyncTask, ctx: TaskContext) -> None:
    if ctx.channel_locked:
        await runtime_locks.release_channel_lock_if_owner(
            task.team_id,
            task.channel_id,
            task.job_id,
        )

    if not ctx.acked:
        await _ack_safely(task)

    if ctx.processing_incremented:
        await job_store.increment_field(task.job_id, "processing_channels", -1)

    await _finalize_job_if_done(task.job_id, task.team_id)


async def _process_task(task: SlackChannelSyncTask, service_cache: dict) -> None:
    """
    채널 단위 작업 오케스트레이션
    """
    ok, _, _ = await _precheck_job(task)
    if not ok:
        return

    ctx = TaskContext()

    try:
        await _start_processing(task, ctx)

        if not ctx.channel_locked:
            await _handle_lock_conflict(task, ctx)
            return

        result = await _execute_channel_sync(task, service_cache)
        await _handle_sync_success(task, result, ctx)

    except Exception as exc:
        await _handle_sync_failure(task, exc, ctx)

    finally:
        await _finalize_task(task, ctx)

async def _consumer_loop(stop_event: asyncio.Event, worker_index: int) -> None:
    service_cache: dict[str, object] = {}

    while not stop_event.is_set():
        try:
            await runtime_queue.flush_due_delayed_to_queue(limit=200)

            task = await runtime_queue.claim_task()
            if task is None:
                await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)
                continue

            await _process_task(task, service_cache)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "[SLACK][FULL SYNC][WORKER] Consumer loop error: worker_index=%s",
                worker_index,
            )
            await asyncio.sleep(settings.SYNC_WORKER_IDLE_SLEEP_SECONDS)


async def run_forever(stop_event: asyncio.Event) -> None:
    moved = await runtime_queue.move_processing_back_to_queue()
    if moved > 0:
        logger.info("[SLACK][FULL SYNC][WORKER] Recovered processing tasks: moved=%s", moved)

    concurrency = max(1, settings.SYNC_WORKER_CHANNEL_CONCURRENCY)
    workers = [
        asyncio.create_task(_consumer_loop(stop_event, index))
        for index in range(concurrency)
    ]

    try:
        await stop_event.wait()
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
