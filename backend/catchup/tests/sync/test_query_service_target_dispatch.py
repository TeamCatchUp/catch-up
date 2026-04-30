from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from catchup.connectors.channel_talk.full_sync_helper import (
    CHANNEL_TALK_FULL_SYNC_TARGET_ID,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
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
from catchup.sync.query_service import SyncQueryService

CHANNEL_ID = "channel-123"
_QUERY_SERVICE_MODULE = "catchup.sync.query_service"
_LOAD_CONNECTION = f"{_QUERY_SERVICE_MODULE}.load_channel_talk_connection"
_LOAD_DOCUMENT_CONNECTION = f"{_QUERY_SERVICE_MODULE}.load_channel_talk_document_connection"
_RUN_IN_THREADPOOL = f"{_QUERY_SERVICE_MODULE}.run_in_threadpool"


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
        space_id="space-123",
        space_name="Help Center",
        access_key="documents-access-key",
        access_secret="documents-access-secret",
        association_status=association_status,
    )


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class SyncQueryServiceDispatchTests(IsolatedAsyncioTestCase):
    async def test_list_targets_realtime_keeps_existing_connector_dispatch_and_adds_channel_talk(self) -> None:
        service = SyncQueryService()

        expectations = {
            SyncConnector.GITHUB: "_list_github_targets",
            SyncConnector.JIRA: "_list_jira_targets",
            SyncConnector.CONFLUENCE: "_list_confluence_targets",
            SyncConnector.SLACK: "_list_slack_targets",
            SyncConnector.CHANNEL_TALK: "_list_channel_talk_targets",
        }

        for connector, method_name in expectations.items():
            sentinel = object()
            for candidate_name in expectations.values():
                setattr(service, candidate_name, AsyncMock(side_effect=AssertionError(candidate_name)))
            selected = AsyncMock(return_value=sentinel)
            setattr(service, method_name, selected)

            result = await service._list_targets_realtime(
                connector=connector,
                scope_id="scope-123",
            )

            self.assertIs(result, sentinel)
            selected.assert_awaited_once_with(scope_id="scope-123")


class ChannelTalkTargetListingTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = SyncQueryService()
        self.run_in_threadpool_patcher = patch(
            _RUN_IN_THREADPOOL,
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_channel_talk_targets_include_only_user_chat_with_base_credentials(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=None,
        ):
            result = await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)

        self.assertEqual(
            [target.target_id for target in result.targets],
            [CHANNEL_TALK_FULL_SYNC_TARGET_ID],
        )
        self.assertTrue(result.targets[0].is_accessible)

    async def test_channel_talk_targets_include_accessible_document_article_when_documents_connected(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=_build_document_connection_record(),
        ):
            result = await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)

        self.assertEqual(
            [target.target_id for target in result.targets],
            [
                CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
            ],
        )
        document_target = result.targets[1]
        self.assertTrue(document_target.is_accessible)
        self.assertEqual(document_target.metadata["target"], "document_article")
        self.assertEqual(document_target.metadata["stage"], "document_article")
        self.assertEqual(document_target.metadata["channel_id"], CHANNEL_ID)
        self.assertEqual(document_target.metadata["space_id"], "space-123")
        self.assertEqual(document_target.metadata["space_name"], "Help Center")
        self.assertNotIn("dispatch_status", document_target.metadata)
        self.assertNotIn("pending_worker_support", document_target.metadata)
        self.assertNotIn("status_reason", document_target.metadata)

    async def test_channel_talk_targets_skip_document_article_when_documents_channel_mismatches(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=_build_document_connection_record(channel_id="channel-other"),
        ):
            result = await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)

        self.assertEqual(
            [target.target_id for target in result.targets],
            [CHANNEL_TALK_FULL_SYNC_TARGET_ID],
        )

    async def test_channel_talk_targets_skip_document_article_when_documents_unverified(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=_build_document_connection_record(
                association_status=ChannelTalkDocumentAssociationStatus.FAILED,
            ),
        ):
            result = await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)

        self.assertEqual(
            [target.target_id for target in result.targets],
            [CHANNEL_TALK_FULL_SYNC_TARGET_ID],
        )

    async def test_channel_talk_targets_skip_document_article_when_documents_lookup_fails(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            side_effect=SQLAlchemyError("document credentials unavailable"),
        ):
            result = await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)

        self.assertEqual(
            [target.target_id for target in result.targets],
            [CHANNEL_TALK_FULL_SYNC_TARGET_ID],
        )

    async def test_channel_talk_targets_reject_missing_base_credentials(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=None,
        ):
            with self.assertRaisesRegex(ValueError, "channel_talk is not connected"):
                await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)

    async def test_channel_talk_targets_reject_base_channel_mismatch(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(channel_id="channel-other"),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Stored Channel Talk credentials do not match the requested channel",
            ):
                await self.service._list_channel_talk_targets(scope_id=CHANNEL_ID)
