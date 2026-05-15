from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.db.incremental.repository import IncrementalRecordChangeInput
from catchup.db.incremental.repository import release_waiting_full_sync_records
from catchup.db.incremental.repository import upsert_waiting_full_sync_record_change
from catchup.db.models import SyncConnector


class _Result:
    def __init__(self, value=None, rowcount: int = 0):
        self.value = value
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self.value


def _payload() -> IncrementalRecordChangeInput:
    return IncrementalRecordChangeInput(
        record_key="channel_talk:channel-123:channel:channel-123:user_chat:chat-123",
        connector=SyncConnector.CHANNEL_TALK,
        scope_id="channel-123",
        record_type="user_chat",
        record_id="chat-123",
        parent_type="channel",
        parent_id="channel-123",
        event_kind="updated",
        last_event_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
        debounce_until=datetime(2026, 5, 14, 10, 0, 5, tzinfo=timezone.utc),
    )


class IncrementalRepositoryWaitingFullSyncTests(TestCase):
    def test_waiting_upsert_conflict_only_updates_existing_waiting_rows(self) -> None:
        db = MagicMock()
        db.execute.return_value = _Result(None)

        state = upsert_waiting_full_sync_record_change(db, _payload())

        self.assertIsNone(state)
        statement = db.execute.call_args.args[0]
        self.assertIn(
            "incremental_record_states.status =",
            str(statement),
        )

    def test_release_uses_waiting_to_debouncing_transition(self) -> None:
        db = MagicMock()
        db.execute.return_value = _Result(rowcount=2)

        with patch(
            "catchup.db.incremental.repository._validate_record_transition"
        ) as validate_transition:
            released = release_waiting_full_sync_records(
                db,
                connector=SyncConnector.CHANNEL_TALK,
                scope_id="channel-123",
                parent_type="channel",
                parent_id="channel-123",
                record_type="user_chat",
            )

        self.assertEqual(released, 2)
        validate_transition.assert_called_once()
        db.commit.assert_called_once()
