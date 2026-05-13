from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.sync.stream_runtime.startup_cleanup import StreamMessageDbState
from catchup.sync.stream_runtime.startup_cleanup import SyncStreamStartupCleanupConfig
from catchup.sync.stream_runtime.startup_cleanup import SyncStreamStartupCleanupResult
from catchup.sync.stream_runtime.startup_cleanup import cleanup_sync_events_stream
from catchup.sync.stream_runtime.startup_cleanup import run_startup_sync_stream_cleanup
from catchup.sync.stream_runtime.startup_cleanup import trim_deadletter_stream


class _FakeRedis:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.commands: list[tuple] = []
        self.entries = [
            (
                "1000-0",
                {
                    "event_id": "event-1",
                    "sync_type": "full",
                },
            ),
            (
                "1001-0",
                {
                    "event_id": "event-2",
                    "sync_type": "full",
                },
            ),
            (
                "1002-0",
                {
                    "event_id": "inc:record:1",
                    "sync_type": "incremental",
                },
            ),
            (
                "1003-0",
                {
                    "event_id": "orphan",
                    "sync_type": "full",
                },
            ),
        ]

    async def xrange(self, name, min="-", max="+", count=None):
        min_id = min
        if min_id == "-":
            start_ms = -1
            start_seq = -1
        else:
            start_ms_text, _, start_seq_text = min_id.partition("-")
            start_ms = int(start_ms_text)
            start_seq = int(start_seq_text)

        max_ms_text, _, max_seq_text = max.partition("-")
        max_ms = int(max_ms_text)
        max_seq = int(max_seq_text)

        result = []
        for message_id, fields in self.entries:
            ms_text, _, seq_text = message_id.partition("-")
            ms = int(ms_text)
            seq = int(seq_text)
            if (ms, seq) < (start_ms, start_seq):
                continue
            if (ms, seq) > (max_ms, max_seq):
                continue
            result.append((message_id, fields))
            if count is not None and len(result) >= count:
                break
        return result

    async def execute_command(self, *args):
        self.commands.append(args)
        if args[0] == "XTRIM":
            return 7
        raise AssertionError(f"unexpected command: {args}")

    async def xpending_range(self, name, groupname, min, max, count):
        self.commands.append(("XPENDING_RANGE", name, groupname, min, max, count))
        return [{"message_id": "1001-0", "consumer": "consumer-1"}]

    async def xdel(self, name, *message_ids):
        self.deleted.extend(message_ids)
        return len(message_ids)


class _FakeControlRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, key):
        self.values.pop(key, None)


def _config(**overrides) -> SyncStreamStartupCleanupConfig:
    values = {
        "version": "test",
        "dry_run": False,
        "retention_days": 1,
        "batch_size": 10,
        "max_batches": 0,
        "lock_ttl_seconds": 60,
        "sleep_seconds": 0.0,
        "dlq_maxlen": 100,
        "delete_orphaned_entries": False,
    }
    values.update(overrides)
    return SyncStreamStartupCleanupConfig(**values)


class SyncStreamStartupCleanupTests(IsolatedAsyncioTestCase):
    async def test_deletes_only_terminal_non_pending_messages(self) -> None:
        redis = _FakeRedis()

        def db_state_loader(message_ids: list[str]) -> StreamMessageDbState:
            self.assertEqual(message_ids, ["1000-0", "1002-0", "1003-0"])
            return StreamMessageDbState(
                known_ids={"1000-0", "1002-0"},
                deletable_ids={"1000-0"},
            )

        result = await cleanup_sync_events_stream(
            config=_config(),
            redis=redis,
            db_state_loader=db_state_loader,
            now=datetime.fromtimestamp(2000000000000 / 1000, tz=timezone.utc),
        )

        self.assertEqual(redis.deleted, ["1000-0"])
        self.assertEqual(result.scanned, 4)
        self.assertEqual(result.deleted, 1)
        self.assertEqual(result.skipped_pending, 1)
        self.assertEqual(result.skipped_not_terminal, 1)
        self.assertEqual(result.skipped_orphaned, 1)
        self.assertIn(
            ("XPENDING_RANGE", "sync:events", "sync:workers", "1000-0", "1003-0", 4),
            redis.commands,
        )

    async def test_can_delete_orphaned_entries_when_enabled(self) -> None:
        redis = _FakeRedis()

        def db_state_loader(message_ids: list[str]) -> StreamMessageDbState:
            return StreamMessageDbState(
                known_ids={"1000-0", "1002-0"},
                deletable_ids={"1000-0"},
            )

        await cleanup_sync_events_stream(
            config=_config(delete_orphaned_entries=True),
            redis=redis,
            db_state_loader=db_state_loader,
            now=datetime.fromtimestamp(2000000000000 / 1000, tz=timezone.utc),
        )

        self.assertEqual(redis.deleted, ["1000-0", "1003-0"])

    async def test_dry_run_does_not_delete(self) -> None:
        redis = _FakeRedis()

        def db_state_loader(message_ids: list[str]) -> StreamMessageDbState:
            return StreamMessageDbState(
                known_ids={"1000-0", "1002-0"},
                deletable_ids={"1000-0"},
            )

        result = await cleanup_sync_events_stream(
            config=_config(dry_run=True),
            redis=redis,
            db_state_loader=db_state_loader,
            now=datetime.fromtimestamp(2000000000000 / 1000, tz=timezone.utc),
        )

        self.assertEqual(redis.deleted, [])
        self.assertEqual(result.deleted, 1)

    async def test_trims_deadletter_stream_with_maxlen(self) -> None:
        redis = _FakeRedis()

        trimmed = await trim_deadletter_stream(config=_config(dlq_maxlen=123), redis=redis)

        self.assertEqual(trimmed, 7)
        self.assertIn(
            ("XTRIM", "sync:events:dlq", "MAXLEN", "~", 123),
            redis.commands,
        )

    async def test_startup_cleanup_uses_trigger_file_and_deletes_it(self) -> None:
        control_redis = _FakeControlRedis()

        async def fake_get_redis_client():
            return control_redis

        async def fake_cleanup(config):
            self.assertEqual(config.version, "trigger-test")
            return SyncStreamStartupCleanupResult(enabled=True, dry_run=False, deleted=3)

        async def fake_trim(config):
            return 2

        with TemporaryDirectory() as tmp_dir:
            trigger_path = Path(tmp_dir) / "startup_cleanup_trigger.json"
            trigger_path.write_text(
                '{"version": "trigger-test", "retention_days": 0}',
                encoding="utf-8",
            )

            with (
                patch(
                    "catchup.sync.stream_runtime.startup_cleanup.get_redis_client",
                    fake_get_redis_client,
                ),
                patch(
                    "catchup.sync.stream_runtime.startup_cleanup.cleanup_sync_events_stream",
                    fake_cleanup,
                ),
                patch(
                    "catchup.sync.stream_runtime.startup_cleanup.trim_deadletter_stream",
                    fake_trim,
                ),
            ):
                result = await run_startup_sync_stream_cleanup(
                    trigger_path=trigger_path,
                )

        self.assertEqual(result.deleted, 3)
        self.assertEqual(result.dlq_trimmed, 2)
        self.assertFalse(trigger_path.exists())

    async def test_startup_cleanup_skips_without_trigger_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            result = await run_startup_sync_stream_cleanup(
                trigger_path=Path(tmp_dir) / "missing.json",
            )

        self.assertFalse(result.enabled)
        self.assertEqual(result.skipped_reason, "trigger_not_found")
