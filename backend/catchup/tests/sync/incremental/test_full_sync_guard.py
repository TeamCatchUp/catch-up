from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import SyncEventKind
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.incremental.full_sync_guard import filter_record_changes_by_full_sync
from catchup.sync.incremental.schemas import RecordChange


def _change(
    *,
    record_type: str = "user_chat",
    parent_type: str = SyncTargetType.CHANNEL,
    parent_id: str = "channel-123",
) -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CHANNEL_TALK,
        scope_id="channel-123",
        record_type=record_type,
        record_id="chat-123",
        parent_type=parent_type,
        parent_id=parent_id,
        event_kind=SyncEventKind.UPDATED,
        last_event_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
    )


@contextmanager
def _patched_full_sync_events(
    *,
    successful: bool,
    active: bool,
) -> Iterator[tuple[MagicMock, MagicMock]]:
    with (
        patch(
            "catchup.sync.incremental.full_sync_guard.has_successful_full_sync_event",
            return_value=successful,
        ) as has_successful,
        patch(
            "catchup.sync.incremental.full_sync_guard.has_active_full_sync_event",
            return_value=active,
        ) as has_active,
    ):
        yield has_successful, has_active


class FullSyncGuardTests(TestCase):
    def test_routes_channel_talk_user_chat_to_waiting_when_channel_target_active(
        self,
    ) -> None:
        with _patched_full_sync_events(successful=False, active=True) as (
            _,
            has_active,
        ):
            result = filter_record_changes_by_full_sync(MagicMock(), [_change()])

        self.assertEqual(len(result.allowed_changes), 0)
        self.assertEqual(len(result.waiting_changes), 1)
        self.assertEqual(len(result.blocked_changes), 0)
        has_active.assert_called_once()
        self.assertEqual(has_active.call_args.kwargs["resource_type"], "channel")
        self.assertEqual(has_active.call_args.kwargs["resource_id"], "channel-123")

    def test_blocks_user_chat_when_channel_target_is_not_active(self) -> None:
        with _patched_full_sync_events(successful=False, active=False):
            result = filter_record_changes_by_full_sync(MagicMock(), [_change()])

        self.assertEqual(len(result.allowed_changes), 0)
        self.assertEqual(len(result.waiting_changes), 0)
        self.assertEqual(len(result.blocked_changes), 1)

    def test_does_not_wait_for_non_user_chat_channel_record(self) -> None:
        with _patched_full_sync_events(successful=False, active=True) as (
            _,
            has_active,
        ):
            result = filter_record_changes_by_full_sync(
                MagicMock(),
                [_change(record_type="other_record")],
            )

        self.assertEqual(len(result.waiting_changes), 0)
        self.assertEqual(len(result.blocked_changes), 1)
        has_active.assert_not_called()

    def test_allows_when_successful_full_sync_exists(self) -> None:
        with _patched_full_sync_events(successful=True, active=False) as (
            _,
            has_active,
        ):
            result = filter_record_changes_by_full_sync(MagicMock(), [_change()])

        self.assertEqual(len(result.allowed_changes), 1)
        self.assertEqual(len(result.waiting_changes), 0)
        self.assertEqual(len(result.blocked_changes), 0)
        has_active.assert_called_once()

    def test_active_user_chat_full_sync_takes_precedence_over_success_history(
        self,
    ) -> None:
        with _patched_full_sync_events(successful=True, active=True) as (
            has_successful,
            _,
        ):
            result = filter_record_changes_by_full_sync(MagicMock(), [_change()])

        self.assertEqual(len(result.allowed_changes), 0)
        self.assertEqual(len(result.waiting_changes), 1)
        self.assertEqual(len(result.blocked_changes), 0)
        has_successful.assert_not_called()
