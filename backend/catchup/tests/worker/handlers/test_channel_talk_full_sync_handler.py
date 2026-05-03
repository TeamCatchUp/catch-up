from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.audit.actions import FullSyncAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import HandlerKey
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import SyncTargetType
from catchup.worker.handlers.channel_talk_full_sync_handler import (
    ChannelTalkFullSyncHandler,
)
from catchup.worker.handlers.channel_talk_incremental_handler import (
    ChannelTalkIncrementalHandler,
)
from catchup.worker.registry import get_ingestion_handler

CHANNEL_ID = "channel-123"
SPACE_ID = "space-123"
_HANDLER_MODULE = "catchup.worker.handlers.channel_talk_full_sync_handler"
_LOAD_CONNECTION = f"{_HANDLER_MODULE}.load_channel_talk_connection"
_LOAD_DOCUMENT_CONNECTION = f"{_HANDLER_MODULE}.load_channel_talk_document_connection"
_RUN_IN_THREADPOOL = f"{_HANDLER_MODULE}.run_in_threadpool"
_RUN_SYNC_INGESTION = f"{_HANDLER_MODULE}.run_sync_ingestion"
_INCREMENTAL_HANDLER_MODULE = (
    "catchup.worker.handlers.channel_talk_incremental_handler"
)
_LOAD_INCREMENTAL_CONNECTION = (
    f"{_INCREMENTAL_HANDLER_MODULE}.load_channel_talk_connection"
)
_LOAD_INCREMENTAL_DOCUMENT_CONNECTION = (
    f"{_INCREMENTAL_HANDLER_MODULE}.load_channel_talk_document_connection"
)
_RUN_INCREMENTAL_THREADPOOL = f"{_INCREMENTAL_HANDLER_MODULE}.run_in_threadpool"
_RUN_INCREMENTAL_SYNC_INGESTION = f"{_INCREMENTAL_HANDLER_MODULE}.run_sync_ingestion"


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


def _build_document_connection_record(
    *,
    channel_id: str = CHANNEL_ID,
    association_status: ChannelTalkDocumentAssociationStatus = (
        ChannelTalkDocumentAssociationStatus.API_VERIFIED
    ),
) -> ChannelTalkDocumentCredentialsRecord:
    return ChannelTalkDocumentCredentialsRecord(
        channel_id=channel_id,
        space_id=SPACE_ID,
        space_name="Help Center",
        access_key="documents-access-key",
        access_secret="documents-access-secret",
        association_status=association_status,
    )


def _build_context(
    *,
    scope_id: str = CHANNEL_ID,
    target_id: str = CHANNEL_ID,
    target_type: SyncTargetType = SyncTargetType.CHANNEL,
    metadata: dict[str, object] | None = None,
) -> FullSyncContext:
    return FullSyncContext(
        event_id="event-123",
        job_id="job-123",
        connector=SyncConnector.CHANNEL_TALK,
        scope_id=scope_id,
        target_type=target_type,
        target_id=target_id,
        target_name=target_id,
        sync_from_ts="1713744000.000000",
        attempt=0,
        max_attempts=3,
        metadata={} if metadata is None else metadata,
    )


def _build_incremental_context(
    *,
    record_type: str = "user_chat",
    record_id: str = "chat-123",
    target_id: str = CHANNEL_ID,
    parent_type: SyncTargetType = SyncTargetType.CHANNEL,
    parent_id: str = CHANNEL_ID,
) -> IncrementalSyncContext:
    return IncrementalSyncContext(
        event_id="event-123",
        job_id="job-123",
        connector=SyncConnector.CHANNEL_TALK,
        scope_id=CHANNEL_ID,
        target_type=SyncTargetType.CHANNEL,
        target_id=target_id,
        target_name=target_id,
        attempt=0,
        max_attempts=3,
        record_key=(
            "channel_talk:channel-123:channel:channel-123:user_chat:chat-123"
        ),
        generation=1,
        record_type=record_type,
        record_id=record_id,
        parent_type=parent_type,
        parent_id=parent_id,
        last_event_at="2026-04-22T12:00:00+00:00",
    )


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _build_application_result(*, persisted_count: int = 0):
    return SimpleNamespace(
        persisted=SimpleNamespace(persisted_count=persisted_count),
    )


class ChannelTalkFullSyncHandlerTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.handler = ChannelTalkFullSyncHandler()
        self.run_in_threadpool_patcher = patch(
            _RUN_IN_THREADPOOL,
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_handler_passes_requested_channel_and_sync_window_to_application(
        self,
    ) -> None:
        fixed_now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
        context = _build_context()

        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _RUN_SYNC_INGESTION,
                AsyncMock(return_value=_build_application_result()),
            ) as run_sync_ingestion,
            patch(
                "catchup.worker.handlers.channel_talk_full_sync_handler.datetime"
            ) as mocked_datetime,
        ):
            mocked_datetime.now.return_value = fixed_now
            mocked_datetime.fromtimestamp.side_effect = lambda value, tz=None: (
                datetime.fromtimestamp(value, tz=tz)
            )

            result = await self.handler.handle(
                context=context,
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        call = run_sync_ingestion.await_args
        self.assertIs(
            call.kwargs["port"],
            self.handler._ingestion_ports[CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET],
        )
        execution = call.kwargs["execution"]
        sync_window = call.kwargs["sync_window"]

        self.assertEqual(execution.channel_id, CHANNEL_ID)
        self.assertEqual(execution.audit_context.connector, context.connector)
        self.assertEqual(execution.audit_context.scope_id, context.scope_id)
        self.assertEqual(execution.audit_context.target_id, context.target_id)
        self.assertEqual(execution.audit_context.job_id, context.job_id)
        self.assertEqual(execution.audit_context.task_id, context.event_id)
        self.assertEqual(
            sync_window.window_start.isoformat(),
            "2024-04-22T00:00:00+00:00",
        )
        self.assertEqual(sync_window.window_end, fixed_now)
        self.assertEqual(result.error_count, 0)
        self.assertFalse(result.skipped)

    async def test_handler_emits_full_sync_event_audit_attempt_and_success(
        self,
    ) -> None:
        context = _build_context()

        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _RUN_SYNC_INGESTION,
                AsyncMock(return_value=_build_application_result(persisted_count=5)),
            ),
            patch("catchup.audit.utils.emit_audit_event") as emit_audit_event,
        ):
            result = await self.handler.handle(
                context=context,
                service_cache={},
            )

        self.assertEqual(result.synced_count, 5)
        self.assertEqual(emit_audit_event.call_count, 2)

        attempt = emit_audit_event.call_args_list[0].kwargs
        self.assertEqual(attempt["action"], FullSyncAction.EVENT)
        self.assertEqual(attempt["status"], AuditStatus.ATTEMPT)
        self.assertIsInstance(attempt["metadata"], FullSyncEventAuditMetadata)
        self.assertEqual(attempt["metadata"].connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(attempt["metadata"].scope_id, CHANNEL_ID)
        self.assertEqual(attempt["metadata"].job_id, "job-123")
        self.assertEqual(attempt["metadata"].event_id, "event-123")
        self.assertEqual(attempt["metadata"].target_type, SyncTargetType.CHANNEL)
        self.assertEqual(attempt["metadata"].target_id, CHANNEL_ID)
        self.assertEqual(attempt["metadata"].phase, "process")
        self.assertFalse(attempt["metadata"].is_retry)

        success = emit_audit_event.call_args_list[1].kwargs
        self.assertEqual(success["action"], FullSyncAction.EVENT)
        self.assertEqual(success["status"], AuditStatus.SUCCESS)
        metadata = success["metadata"]
        self.assertIsInstance(metadata, FullSyncEventAuditMetadata)
        self.assertEqual(metadata.synced_count, 5)
        self.assertEqual(metadata.error_count, 0)
        self.assertFalse(metadata.skipped)

    async def test_handler_emits_full_sync_event_audit_failure(
        self,
    ) -> None:
        with patch("catchup.audit.utils.emit_audit_event") as emit_audit_event:
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk target_type must be one of: channel, space",
            ):
                await self.handler.handle(
                    context=_build_context(
                        target_id=CHANNEL_ID,
                        target_type=SyncTargetType.RESOURCE,
                    ),
                    service_cache={},
                )

        self.assertEqual(emit_audit_event.call_count, 2)
        attempt = emit_audit_event.call_args_list[0].kwargs
        self.assertEqual(attempt["action"], FullSyncAction.EVENT)
        self.assertEqual(attempt["status"], AuditStatus.ATTEMPT)

        failure = emit_audit_event.call_args_list[1].kwargs
        self.assertEqual(failure["action"], FullSyncAction.EVENT)
        self.assertEqual(failure["status"], AuditStatus.FAILURE)
        self.assertEqual(failure["level"], AuditLevel.WARNING)
        metadata = failure["metadata"]
        self.assertIsInstance(metadata, FullSyncEventAuditMetadata)
        self.assertEqual(metadata.connector, SyncConnector.CHANNEL_TALK)
        self.assertIsNone(metadata.context)
        self.assertIsNone(metadata.error_summary)

    async def test_handler_rejects_unknown_target_type(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk target_type must be one of: channel, space",
            ):
                await self.handler.handle(
                    context=_build_context(
                        target_id=CHANNEL_ID,
                        target_type=SyncTargetType.RESOURCE,
                    ),
                    service_cache={},
                )

    async def test_handler_routes_channel_without_metadata(self) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _RUN_SYNC_INGESTION,
                AsyncMock(return_value=_build_application_result()),
            ) as run_sync_ingestion,
        ):
            await self.handler.handle(
                context=_build_context(metadata={}),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        self.assertIs(
            run_sync_ingestion.await_args.kwargs["port"],
            self.handler._ingestion_ports[CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET],
        )

    async def test_handler_routes_document_article_to_document_application(
        self,
    ) -> None:
        base_connection = _build_connection_record()
        document_connection = _build_document_connection_record()

        with (
            patch(
                _LOAD_CONNECTION,
                return_value=base_connection,
            ),
            patch(
                _LOAD_DOCUMENT_CONNECTION,
                return_value=document_connection,
            ) as load_document_connection,
            patch(
                _RUN_SYNC_INGESTION,
                AsyncMock(return_value=_build_application_result()),
            ) as run_sync_ingestion,
        ):
            result = await self.handler.handle(
                context=_build_context(
                    target_id=SPACE_ID,
                    target_type=SyncTargetType.SPACE,
                    metadata={},
                ),
                service_cache={},
            )

        load_document_connection.assert_called_once()
        args = load_document_connection.call_args.args
        kwargs = load_document_connection.call_args.kwargs
        self.assertEqual(args[0], CHANNEL_ID)
        self.assertEqual(
            kwargs.get("space_id", args[1] if len(args) > 1 else None),
            SPACE_ID,
        )
        run_sync_ingestion.assert_awaited_once()
        self.assertIs(
            run_sync_ingestion.await_args.kwargs["port"],
            self.handler._ingestion_ports[
                CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
            ],
        )
        execution = run_sync_ingestion.await_args.kwargs["execution"]

        self.assertEqual(
            execution.target,
            CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
        )
        self.assertEqual(execution.channel_id, CHANNEL_ID)
        self.assertIs(execution.channel_connection, base_connection)
        self.assertIs(execution.document_connection, document_connection)
        self.assertEqual(execution.space_id, SPACE_ID)
        self.assertEqual(execution.space_name, "Help Center")
        self.assertEqual(
            execution.audit_context.target_id,
            SPACE_ID,
        )
        self.assertEqual(result.synced_count, 0)
        self.assertEqual(result.error_count, 0)

    async def test_handler_rejects_document_article_when_documents_missing(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LOAD_DOCUMENT_CONNECTION,
                return_value=None,
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk documents is not connected for the requested channel",
            ):
                await self.handler.handle(
                    context=_build_context(
                        target_id=SPACE_ID,
                        target_type=SyncTargetType.SPACE,
                        metadata={},
                    ),
                    service_cache={},
                )

    async def test_handler_rejects_document_article_when_documents_channel_mismatches(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LOAD_DOCUMENT_CONNECTION,
                return_value=_build_document_connection_record(
                    channel_id="channel-other"
                ),
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Stored Channel Talk Documents credentials do not match the "
                "requested channel",
            ):
                await self.handler.handle(
                    context=_build_context(
                        target_id=SPACE_ID,
                        target_type=SyncTargetType.SPACE,
                        metadata={},
                    ),
                    service_cache={},
                )

    async def test_handler_rejects_document_article_when_documents_unverified(
        self,
    ) -> None:
        with (
            patch(
                _LOAD_CONNECTION,
                return_value=_build_connection_record(),
            ),
            patch(
                _LOAD_DOCUMENT_CONNECTION,
                return_value=_build_document_connection_record(
                    association_status=ChannelTalkDocumentAssociationStatus.FAILED,
                ),
            ),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk documents credentials are not API verified for "
                "the requested channel",
            ):
                await self.handler.handle(
                    context=_build_context(
                        target_id=SPACE_ID,
                        target_type=SyncTargetType.SPACE,
                        metadata={},
                    ),
                    service_cache={},
                )

    async def test_handler_rejects_missing_connection(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=None,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "channel_talk is not connected for the requested channel",
            ):
                await self.handler.handle(
                    context=_build_context(),
                    service_cache={},
                )

    async def test_handler_rejects_requested_channel_mismatch(self) -> None:
        with patch(
            _LOAD_CONNECTION,
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


class ChannelTalkIncrementalHandlerTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.handler = ChannelTalkIncrementalHandler()
        self.run_in_threadpool_patcher = patch(
            _RUN_INCREMENTAL_THREADPOOL,
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_handler_syncs_user_chat_record_by_id(self) -> None:
        with patch(
            _RUN_INCREMENTAL_SYNC_INGESTION,
            AsyncMock(return_value=_build_application_result(persisted_count=3)),
        ) as run_sync_ingestion:
            result = await self.handler.handle(
                context=_build_incremental_context(
                    record_type="user_chat",
                    record_id="chat-123",
                ),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        call = run_sync_ingestion.await_args
        self.assertIs(call.kwargs["port"], self.handler._user_chat_adapter)
        self.assertEqual(call.kwargs["execution"].user_chat_id, "chat-123")
        self.assertEqual(call.kwargs["execution"].channel_id, CHANNEL_ID)
        self.assertEqual(
            call.kwargs["sync_window"].window_start.isoformat(),
            "2026-04-22T12:00:00+00:00",
        )
        self.assertEqual(result.synced_count, 3)
        self.assertEqual(result.error_count, 0)

    async def test_handler_syncs_document_article_with_channel_and_space_credentials(
        self,
    ) -> None:
        channel_connection = _build_connection_record()
        document_connection = _build_document_connection_record()

        with (
            patch(
                _LOAD_INCREMENTAL_CONNECTION,
                return_value=channel_connection,
            ) as load_connection,
            patch(
                _LOAD_INCREMENTAL_DOCUMENT_CONNECTION,
                return_value=document_connection,
            ) as load_document_connection,
            patch(
                _RUN_INCREMENTAL_SYNC_INGESTION,
                AsyncMock(return_value=_build_application_result(persisted_count=2)),
            ) as run_sync_ingestion,
        ):
            result = await self.handler.handle(
                context=_build_incremental_context(
                    record_type="document_article",
                    record_id="article-123",
                    target_id=SPACE_ID,
                    parent_type=SyncTargetType.SPACE,
                    parent_id=SPACE_ID,
                ),
                service_cache={},
            )

        load_connection.assert_called_once_with(CHANNEL_ID)
        load_document_connection.assert_called_once_with(CHANNEL_ID, SPACE_ID)
        run_sync_ingestion.assert_awaited_once()
        call = run_sync_ingestion.await_args
        self.assertIs(call.kwargs["port"], self.handler._article_adapter)
        execution = call.kwargs["execution"]
        self.assertEqual(execution.article_id, "article-123")
        self.assertIs(execution.channel_connection, channel_connection)
        self.assertIs(execution.document_connection, document_connection)
        self.assertEqual(execution.channel_id, CHANNEL_ID)
        self.assertEqual(execution.space_id, SPACE_ID)
        self.assertEqual(result.synced_count, 2)
        self.assertEqual(result.error_count, 0)


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

    def test_worker_registry_includes_channel_talk_incremental_handler(self) -> None:
        self.assertIsNotNone(
            get_ingestion_handler(
                connector=SyncConnector.CHANNEL_TALK,
                sync_type=SyncType.INCREMENTAL,
            ),
        )
