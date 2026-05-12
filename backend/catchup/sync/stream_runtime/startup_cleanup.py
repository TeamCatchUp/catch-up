from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Callable
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from redis.exceptions import ResponseError
from sqlalchemy import select

from catchup.db.engine import SessionLocal
from catchup.db.models import IncrementalOutboxStatus
from catchup.db.models import IncrementalRecordState
from catchup.db.models import IncrementalRecordStatus
from catchup.db.models import IncrementalStreamOutbox
from catchup.db.models import SyncEvent
from catchup.db.models import SyncEventPublishStatus
from catchup.db.models import SyncEventStatus
from catchup.sync.stream_runtime.stream_constants import SYNC_EVENTS_CONSUMER_GROUP
from catchup.sync.stream_runtime.stream_constants import (
    SYNC_EVENTS_DEADLETTER_STREAM_KEY,
)
from catchup.sync.stream_runtime.stream_constants import SYNC_EVENTS_STREAM_KEY
from catchup.utils.redis import get_redis_client
from catchup.utils.redis import get_stream_redis_client

logger = logging.getLogger(__name__)

_CLEANUP_KEY_PREFIX = "sync:events:startup-cleanup"
_DEFAULT_TRIGGER_PATH = Path(__file__).with_name("startup_cleanup_trigger.json")
_DEFAULT_TRIGGER_VALUES = {
    "version": "202605_sync_stream_cleanup_v1",
    "dry_run": False,
    "retention_days": 7,
    "batch_size": 1000,
    "max_batches": 0,
    "lock_ttl_seconds": 21600,
    "sleep_seconds": 0.0,
    "dlq_maxlen": 100000,
    "delete_orphaned_entries": False,
}


@dataclass(slots=True, frozen=True)
class StreamMessageDbState:
    known_ids: set[str]
    deletable_ids: set[str]


@dataclass(slots=True, frozen=True)
class SyncStreamStartupCleanupConfig:
    version: str
    dry_run: bool
    retention_days: int
    batch_size: int
    max_batches: int
    lock_ttl_seconds: int
    sleep_seconds: float
    dlq_maxlen: int
    delete_orphaned_entries: bool

    @classmethod
    def from_trigger_file(cls, trigger_path: Path) -> "SyncStreamStartupCleanupConfig":
        raw_text = trigger_path.read_text(encoding="utf-8").strip()
        trigger_values = json.loads(raw_text) if raw_text else {}
        if not isinstance(trigger_values, dict):
            raise ValueError(
                f"startup cleanup trigger must be a JSON object: {trigger_path}",
            )

        values = _DEFAULT_TRIGGER_VALUES | trigger_values
        return cls(
            version=str(values["version"]),
            dry_run=bool(values["dry_run"]),
            retention_days=max(0, int(values["retention_days"])),
            batch_size=max(1, int(values["batch_size"])),
            max_batches=max(0, int(values["max_batches"])),
            lock_ttl_seconds=max(1, int(values["lock_ttl_seconds"])),
            sleep_seconds=max(0.0, float(values["sleep_seconds"])),
            dlq_maxlen=max(0, int(values["dlq_maxlen"])),
            delete_orphaned_entries=bool(values["delete_orphaned_entries"]),
        )


@dataclass(slots=True)
class SyncStreamStartupCleanupResult:
    enabled: bool
    dry_run: bool
    skipped_reason: str | None = None
    scanned: int = 0
    deleted: int = 0
    skipped_pending: int = 0
    skipped_not_terminal: int = 0
    skipped_orphaned: int = 0
    batches: int = 0
    dlq_trimmed: int = 0
    cutoff_id: str | None = None

    def to_log_fields(self) -> dict[str, Any]:
        return asdict(self)


DbStateLoader = Callable[[list[str]], StreamMessageDbState]


def _decode_redis_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _stream_id_for_datetime(value: datetime) -> str:
    resolved = value
    if resolved.tzinfo is None:
        resolved = resolved.replace(tzinfo=timezone.utc)
    resolved = resolved.astimezone(timezone.utc)
    return f"{int(resolved.timestamp() * 1000)}-0"


def _next_stream_id(message_id: str) -> str:
    milliseconds, _, sequence = message_id.partition("-")
    if not milliseconds or not sequence:
        raise ValueError(f"invalid redis stream id: {message_id}")
    return f"{milliseconds}-{int(sequence) + 1}"


def _normalize_stream_entry(raw_entry: tuple[Any, Any]) -> tuple[str, dict[str, str]]:
    raw_message_id, raw_fields = raw_entry
    message_id = _decode_redis_value(raw_message_id)
    fields = {
        _decode_redis_value(key): _decode_redis_value(value)
        for key, value in dict(raw_fields).items()
    }
    return message_id, fields


def _load_deletable_stream_message_ids_sync(
    message_ids: list[str],
) -> StreamMessageDbState:
    if not message_ids:
        return StreamMessageDbState(known_ids=set(), deletable_ids=set())

    with SessionLocal() as db:
        full_rows = db.execute(
            select(SyncEvent.stream_message_id).where(
                SyncEvent.stream_message_id.in_(message_ids),
                SyncEvent.publish_status == SyncEventPublishStatus.PUBLISHED,
                SyncEvent.status.in_(
                    [
                        SyncEventStatus.SUCCESS,
                        SyncEventStatus.FAILED,
                    ]
                ),
            )
        ).scalars()
        full_ids = {message_id for message_id in full_rows if message_id}

        incremental_rows = db.execute(
            select(IncrementalStreamOutbox.stream_message_id)
            .join(
                IncrementalRecordState,
                IncrementalRecordState.record_key == IncrementalStreamOutbox.record_key,
            )
            .where(
                IncrementalStreamOutbox.stream_message_id.in_(message_ids),
                IncrementalStreamOutbox.status == IncrementalOutboxStatus.PUBLISHED,
                IncrementalRecordState.status.in_(
                    [
                        IncrementalRecordStatus.SYNCED,
                        IncrementalRecordStatus.DEAD,
                        IncrementalRecordStatus.RECOVERED,
                    ]
                ),
            )
        ).scalars()
        incremental_ids = {
            message_id for message_id in incremental_rows if message_id
        }

        known_full_rows = db.execute(
            select(SyncEvent.stream_message_id).where(
                SyncEvent.stream_message_id.in_(message_ids),
            )
        ).scalars()
        known_incremental_rows = db.execute(
            select(IncrementalStreamOutbox.stream_message_id).where(
                IncrementalStreamOutbox.stream_message_id.in_(message_ids),
            )
        ).scalars()
        known_ids = {
            message_id
            for message_id in list(known_full_rows) + list(known_incremental_rows)
            if message_id
        }

    deletable_ids = full_ids | incremental_ids
    return StreamMessageDbState(known_ids=known_ids, deletable_ids=deletable_ids)


async def _pending_ids_for_range(
    redis: Any,
    *,
    start_id: str,
    end_id: str,
    count: int,
) -> set[str]:
    try:
        raw_pending = await redis.xpending_range(
            SYNC_EVENTS_STREAM_KEY,
            SYNC_EVENTS_CONSUMER_GROUP,
            min=start_id,
            max=end_id,
            count=max(1, count),
        )
    except ResponseError as exc:
        if "NOGROUP" in str(exc):
            return set()
        raise

    pending_ids: set[str] = set()
    for row in raw_pending or []:
        if isinstance(row, dict):
            message_id = row.get("message_id")
            if message_id is not None:
                pending_ids.add(_decode_redis_value(message_id))
            continue
        if isinstance(row, (list, tuple)) and row:
            pending_ids.add(_decode_redis_value(row[0]))
    return pending_ids


async def cleanup_sync_events_stream(
    *,
    config: SyncStreamStartupCleanupConfig,
    redis: Any | None = None,
    db_state_loader: DbStateLoader | None = None,
    now: datetime | None = None,
) -> SyncStreamStartupCleanupResult:
    stream_redis = redis or await get_stream_redis_client()
    cutoff_at = (now or datetime.now(timezone.utc)) - timedelta(
        days=max(0, int(config.retention_days))
    )
    cutoff_id = _stream_id_for_datetime(cutoff_at)
    result = SyncStreamStartupCleanupResult(
        enabled=True,
        dry_run=config.dry_run,
        cutoff_id=cutoff_id,
    )

    next_start_id = "-"
    while True:
        if config.max_batches > 0 and result.batches >= config.max_batches:
            break

        raw_entries = await stream_redis.xrange(
            SYNC_EVENTS_STREAM_KEY,
            min=next_start_id,
            max=cutoff_id,
            count=max(1, int(config.batch_size)),
        )
        if not raw_entries:
            break

        entries = [_normalize_stream_entry(entry) for entry in raw_entries]
        message_ids = [message_id for message_id, _ in entries]
        pending_ids = await _pending_ids_for_range(
            stream_redis,
            start_id=message_ids[0],
            end_id=message_ids[-1],
            count=len(message_ids),
        )
        candidate_ids = [
            message_id for message_id in message_ids if message_id not in pending_ids
        ]

        if db_state_loader is None:
            db_state = await run_in_threadpool(
                _load_deletable_stream_message_ids_sync,
                candidate_ids,
            )
        else:
            db_state = db_state_loader(candidate_ids)

        orphaned_ids = set(candidate_ids) - db_state.known_ids
        delete_ids = set(db_state.deletable_ids)
        if config.delete_orphaned_entries:
            delete_ids |= orphaned_ids

        result.scanned += len(message_ids)
        result.skipped_pending += len(pending_ids)
        result.skipped_orphaned += len(orphaned_ids)
        result.skipped_not_terminal += len(
            set(candidate_ids) - db_state.deletable_ids - orphaned_ids
        )
        result.batches += 1

        if delete_ids:
            sorted_delete_ids = sorted(delete_ids)
            if config.dry_run:
                result.deleted += len(sorted_delete_ids)
            else:
                deleted = await stream_redis.xdel(
                    SYNC_EVENTS_STREAM_KEY,
                    *sorted_delete_ids,
                )
                result.deleted += int(deleted)

        next_start_id = _next_stream_id(message_ids[-1])

        if config.sleep_seconds > 0:
            await asyncio.sleep(config.sleep_seconds)

    return result


async def trim_deadletter_stream(
    *,
    config: SyncStreamStartupCleanupConfig,
    redis: Any | None = None,
) -> int:
    if config.dlq_maxlen <= 0:
        return 0
    if config.dry_run:
        return 0

    stream_redis = redis or await get_stream_redis_client()
    trimmed = await stream_redis.execute_command(
        "XTRIM",
        SYNC_EVENTS_DEADLETTER_STREAM_KEY,
        "MAXLEN",
        "~",
        int(config.dlq_maxlen),
    )
    return int(trimmed or 0)


async def run_startup_sync_stream_cleanup(
    config: SyncStreamStartupCleanupConfig | None = None,
    trigger_path: Path | str | None = _DEFAULT_TRIGGER_PATH,
) -> SyncStreamStartupCleanupResult:
    resolved_trigger_path = Path(trigger_path) if trigger_path is not None else None
    if config is None:
        if resolved_trigger_path is None or not resolved_trigger_path.exists():
            return SyncStreamStartupCleanupResult(
                enabled=False,
                dry_run=False,
                skipped_reason="trigger_not_found",
            )
        resolved_config = SyncStreamStartupCleanupConfig.from_trigger_file(
            resolved_trigger_path,
        )
    else:
        resolved_config = config

    if not resolved_config.version.strip():
        return SyncStreamStartupCleanupResult(
            enabled=False,
            dry_run=resolved_config.dry_run,
            skipped_reason="empty_version",
        )

    redis = await get_redis_client()
    lock_key = f"{_CLEANUP_KEY_PREFIX}:{resolved_config.version}:lock"
    done_key = f"{_CLEANUP_KEY_PREFIX}:{resolved_config.version}:done"
    token = str(uuid4())

    if await redis.get(done_key):
        if resolved_trigger_path is not None and not resolved_config.dry_run:
            _delete_trigger_file(resolved_trigger_path)
        return SyncStreamStartupCleanupResult(
            enabled=True,
            dry_run=resolved_config.dry_run,
            skipped_reason="already_done",
        )

    acquired = await redis.set(
        lock_key,
        token,
        nx=True,
        ex=max(1, int(resolved_config.lock_ttl_seconds)),
    )
    if not acquired:
        return SyncStreamStartupCleanupResult(
            enabled=True,
            dry_run=resolved_config.dry_run,
            skipped_reason="lock_not_acquired",
        )

    try:
        result = await cleanup_sync_events_stream(config=resolved_config)
        result.dlq_trimmed = await trim_deadletter_stream(config=resolved_config)
        if not resolved_config.dry_run:
            await redis.set(
                done_key,
                json.dumps(result.to_log_fields(), sort_keys=True),
            )
            if resolved_trigger_path is not None:
                _delete_trigger_file(resolved_trigger_path)
        logger.info(
            "[SYNC][STREAM][CLEANUP] Startup cleanup completed: %s",
            result.to_log_fields(),
        )
        return result
    finally:
        current_token = await redis.get(lock_key)
        if _decode_redis_value(current_token) == token:
            await redis.delete(lock_key)


def _delete_trigger_file(trigger_path: Path) -> None:
    try:
        trigger_path.unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "[SYNC][STREAM][CLEANUP] Failed to delete trigger file: %s",
            trigger_path,
            exc_info=True,
        )


async def _main() -> None:
    result = await run_startup_sync_stream_cleanup()
    print(json.dumps(result.to_log_fields(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
