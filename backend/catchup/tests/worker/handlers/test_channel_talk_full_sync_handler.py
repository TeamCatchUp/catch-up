from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.connectors.channel_talk.full_sync_helper import (
    CHANNEL_TALK_FULL_SYNC_TARGET_ID,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import HandlerKey
from catchup.sync.common.schemas import SyncTargetType
from catchup.worker.handlers.channel_talk_full_sync_handler import (
    ChannelTalkFullSyncHandler,
)
from catchup.worker.registry import get_ingestion_handler

CHANNEL_ID = "channel-123"


def _build_connection_record(
    *,
    channel_id: str = CHANNEL_ID,
) -> ChannelTalkCredentialsRecord:
    return ChannelTalkCredentialsRecord(
        channel_id=channel_id,
        channel_name="Support",
        access_key="access-key",
        access_secret="access-secret",
        webhook_token="webhook-token",
    )


def _build_context(
    *,
    scope_id: str = CHANNEL_ID,
    target_id: str = CHANNEL_TALK_FULL_SYNC_TARGET_ID,
) -> FullSyncContext:
    return FullSyncContext(
        event_id="event-123",
        job_id="job-123",
        connector=SyncConnector.CHANNEL_TALK,
        scope_id=scope_id,
        target_type=SyncTargetType.RESOURCE,
        target_id=target_id,
        target_name=target_id,
        sync_from_ts="1713744000.000000",
        attempt=0,
        max_attempts=3,
        metadata={},
    )


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class ChannelTalkFullSyncHandlerTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.handler = ChannelTalkFullSyncHandler()
        self.run_in_threadpool_patcher = patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.run_in_threadpool",
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_handler_passes_requested_channel_and_sync_window_to_application(
        self,
    ) -> None:
        fixed_now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
        application_result = type(
            "_ApplicationResult",
            (),
            {
                "persisted": type(
                    "_PersistedResult",
                    (),
                    {"persisted_count": 0},
                )(),
            },
        )()
        self.handler._application.run_full_sync = AsyncMock(
            return_value=application_result
        )
        context = _build_context()

        with patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.load_channel_talk_connection",
            return_value=_build_connection_record(),
        ), patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.datetime"
        ) as mocked_datetime:
            mocked_datetime.now.return_value = fixed_now
            mocked_datetime.fromtimestamp.side_effect = (
                lambda value, tz=None: datetime.fromtimestamp(value, tz=tz)
            )

            result = await self.handler.handle(
                context=context,
                service_cache={},
            )

        self.handler._application.run_full_sync.assert_awaited_once()
        execution = self.handler._application.run_full_sync.await_args.kwargs["execution"]
        sync_window = self.handler._application.run_full_sync.await_args.kwargs["sync_window"]

        self.assertEqual(execution.channel_id, CHANNEL_ID)
        self.assertEqual(execution.audit_context.connector, context.connector)
        self.assertEqual(execution.audit_context.scope_id, context.scope_id)
        self.assertEqual(execution.audit_context.target_id, context.target_id)
        self.assertEqual(execution.audit_context.job_id, context.job_id)
        self.assertEqual(execution.audit_context.task_id, context.event_id)
        self.assertEqual(sync_window.window_start.isoformat(), "2024-04-22T00:00:00+00:00")
        self.assertEqual(sync_window.window_end, fixed_now)
        self.assertEqual(result.error_count, 0)
        self.assertFalse(result.skipped)

    async def test_handler_rejects_non_user_chat_target(self) -> None:
        with patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.load_channel_talk_connection",
            return_value=_build_connection_record(),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk target_id must be user_chat",
            ):
                await self.handler.handle(
                    context=_build_context(target_id="group"),
                    service_cache={},
                )

    async def test_handler_does_not_accept_document_article_yet(self) -> None:
        with patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.load_channel_talk_connection",
            return_value=_build_connection_record(),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk target_id must be user_chat",
            ):
                await self.handler.handle(
                    context=_build_context(
                        target_id=CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
                    ),
                    service_cache={},
                )

    async def test_handler_rejects_missing_connection(self) -> None:
        with patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.load_channel_talk_connection",
            return_value=None,
        ):
            with self.assertRaisesRegex(ValueError, "channel_talk is not connected"):
                await self.handler.handle(
                    context=_build_context(),
                    service_cache={},
                )

    async def test_handler_rejects_requested_channel_mismatch(self) -> None:
        with patch(
            "catchup.worker.handlers.channel_talk_full_sync_handler.load_channel_talk_connection",
            return_value=_build_connection_record(channel_id="channel-other"),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Stored Channel Talk credentials do not match the requested channel",
            ):
                await self.handler.handle(
                    context=_build_context(),
                    service_cache={},
                )


class WorkerRegistryAdmissionTests(TestCase):
    def test_worker_registry_includes_channel_talk_full_handler(self) -> None:
        self.assertIsNotNone(
            get_ingestion_handler(
                connector=SyncConnector.CHANNEL_TALK,
                sync_type=SyncType.FULL,
            ),
        )
        self.assertEqual(
            HandlerKey.of(
                connector=SyncConnector.CHANNEL_TALK,
                sync_type=SyncType.FULL,
            ).connector,
            SyncConnector.CHANNEL_TALK,
        )

    def test_worker_registry_keeps_existing_incremental_handlers_registered(
        self,
    ) -> None:
        for connector in (
            SyncConnector.SLACK,
            SyncConnector.GITHUB,
            SyncConnector.JIRA,
            SyncConnector.CONFLUENCE,
        ):
            self.assertIsNotNone(
                get_ingestion_handler(
                    connector=connector,
                    sync_type=SyncType.INCREMENTAL,
                ),
            )
