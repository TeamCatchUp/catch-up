from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import SyncEventKind
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.incremental.persist import persist_incremental_changes
from catchup.sync.incremental.schemas import RecordChange


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        return None


def _change(record_id: str = "chat-123") -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CHANNEL_TALK,
        scope_id="channel-123",
        record_type="user_chat",
        record_id=record_id,
        parent_type=SyncTargetType.CHANNEL,
        parent_id="channel-123",
        event_kind=SyncEventKind.UPDATED,
        last_event_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
    )


def _guard_result(
    *,
    allowed_changes: list[RecordChange] | None = None,
    waiting_changes: list[RecordChange] | None = None,
    blocked_changes: list[RecordChange] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        allowed_changes=allowed_changes or [],
        waiting_changes=waiting_changes or [],
        blocked_changes=blocked_changes or [],
        blocked_targets=[],
    )


class PersistIncrementalChangesTests(TestCase):
    def test_persists_waiting_changes_and_does_not_count_them_as_blocked(self) -> None:
        change = _change()
        guard_result = _guard_result(waiting_changes=[change])

        with (
            patch(
                "catchup.sync.incremental.persist.SessionLocal",
                return_value=_FakeSession(),
            ),
            patch(
                "catchup.sync.incremental.persist.filter_record_changes_by_full_sync",
                return_value=guard_result,
            ),
            patch(
                "catchup.sync.incremental.persist.upsert_waiting_full_sync_record_change",
                return_value=SimpleNamespace(record_key=change.record_key),
            ) as upsert_waiting,
        ):
            result = persist_incremental_changes([change])

        upsert_waiting.assert_called_once()
        self.assertEqual(result.record_keys, [change.record_key])
        self.assertEqual(result.blocked_count, 0)
        self.assertEqual(result.first_allowed_change, change)

    def test_skipped_waiting_conflict_is_not_reported_as_accepted(self) -> None:
        change = _change()
        guard_result = _guard_result(waiting_changes=[change])

        with (
            patch(
                "catchup.sync.incremental.persist.SessionLocal",
                return_value=_FakeSession(),
            ),
            patch(
                "catchup.sync.incremental.persist.filter_record_changes_by_full_sync",
                return_value=guard_result,
            ),
            patch(
                "catchup.sync.incremental.persist.upsert_waiting_full_sync_record_change",
                return_value=None,
            ),
        ):
            result = persist_incremental_changes([change])

        self.assertEqual(result.record_keys, [])
        self.assertEqual(result.blocked_count, 0)
        self.assertIsNone(result.first_allowed_change)

    def test_allowed_and_waiting_records_are_both_returned(self) -> None:
        allowed = _change("chat-allowed")
        waiting = _change("chat-waiting")
        guard_result = _guard_result(
            allowed_changes=[allowed],
            waiting_changes=[waiting],
        )

        with (
            patch(
                "catchup.sync.incremental.persist.SessionLocal",
                return_value=_FakeSession(),
            ),
            patch(
                "catchup.sync.incremental.persist.filter_record_changes_by_full_sync",
                return_value=guard_result,
            ),
            patch(
                "catchup.sync.incremental.persist.upsert_record_change",
                return_value=SimpleNamespace(record_key=allowed.record_key),
            ),
            patch(
                "catchup.sync.incremental.persist.upsert_waiting_full_sync_record_change",
                return_value=SimpleNamespace(record_key=waiting.record_key),
            ),
        ):
            result = persist_incremental_changes([allowed, waiting])

        self.assertEqual(result.record_keys, [allowed.record_key, waiting.record_key])
        self.assertEqual(result.first_allowed_change, allowed)
