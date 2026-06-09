from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.repair.context import RecordRepairContext
from catchup.sync.repair.protocols import RecordRepairHandler
from catchup.sync.repair.record_repair_service import RecordRepairService
from catchup.sync.repair.registry import RecordRepairHandlerRegistry


def _repair_registry(
    overrides: dict[SyncConnector, RecordRepairHandler] | None = None,
) -> RecordRepairHandlerRegistry:
    handlers: dict[SyncConnector, RecordRepairHandler] = {
        SyncConnector.CHANNEL_TALK: MagicMock(),
        SyncConnector.CONFLUENCE: MagicMock(),
        SyncConnector.GITHUB: MagicMock(),
        SyncConnector.JIRA: MagicMock(),
        SyncConnector.SLACK: MagicMock(),
    }
    if overrides:
        handlers.update(overrides)
    return RecordRepairHandlerRegistry(handlers=handlers)


class RecordRepairServiceStatusTests(IsolatedAsyncioTestCase):
    async def test_mark_retry_event_success_commits_status_update(self) -> None:
        service = RecordRepairService(registry=_repair_registry())
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


class RecordRepairHandlerRegistryTests(TestCase):
    def test_registry_returns_connector_handler(self) -> None:
        handler = MagicMock()
        registry = _repair_registry({SyncConnector.CHANNEL_TALK: handler})

        self.assertIs(
            registry.handler_for(SyncConnector.CHANNEL_TALK),
            handler,
        )

    def test_registry_rejects_unsupported_connector(self) -> None:
        registry = RecordRepairHandlerRegistry(handlers={})

        with self.assertRaises(SyncRequestException) as raised:
            registry.handler_for(SyncConnector.CHANNEL_TALK)

        self.assertEqual(raised.exception.code, "unsupported_connector")
        self.assertEqual(
            raised.exception.metadata,
            {"connector": SyncConnector.CHANNEL_TALK.value},
        )
