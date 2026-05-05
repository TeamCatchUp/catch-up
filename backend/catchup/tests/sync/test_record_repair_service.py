from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.repair.context import RecordRepairContext
from catchup.sync.repair.record_repair_service import RecordRepairService


class RecordRepairServiceStatusTests(IsolatedAsyncioTestCase):
    async def test_mark_retry_event_success_commits_status_update(self) -> None:
        service = RecordRepairService(
            channel_talk_handler=MagicMock(),
            confluence_handler=MagicMock(),
            github_handler=MagicMock(),
            jira_handler=MagicMock(),
            slack_handler=MagicMock(),
        )
        repair_context = RecordRepairContext(
            event_id="event-123",
            attempt=1,
            event_status=SyncEventStatus.FAILED,
            connector=SyncConnector.CHANNEL_TALK,
            scope_id="channel-123",
            target_type=SyncTargetType.CHANNEL,
            target_id="channel-123",
            target_name="Support",
            sync_from_ts="1777584000",
            sync_from_dt=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        db = MagicMock()
        session_factory = MagicMock()
        session_factory.return_value.__enter__.return_value = db

        with (
            patch(
                "catchup.sync.repair.record_repair_service.SessionLocal",
                session_factory,
            ),
            patch(
                "catchup.sync.repair.record_repair_service.finalize_manual_retry_success",
                return_value=True,
            ) as finalize_success,
        ):
            status = await service._mark_retry_event_status(
                repair_context=repair_context,
                has_retry_failure=False,
            )

        self.assertEqual(status, SyncEventStatus.SUCCESS)
        finalize_success.assert_called_once_with(db, "event-123")
        db.commit.assert_called_once_with()
