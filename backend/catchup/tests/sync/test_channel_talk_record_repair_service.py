from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

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
from catchup.db.models import SyncEventStatus
from catchup.server.sync.schemas import SyncRecordRetryItemRequest
from catchup.server.sync.schemas import SyncRecordRetryRequest
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.repair.channel_talk_record_repair_service import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE,
)
from catchup.sync.repair.channel_talk_record_repair_service import (
    CHANNEL_TALK_USER_CHAT_RECORD_TYPE,
)
from catchup.sync.repair.channel_talk_record_repair_service import (
    ChannelTalkRecordRepairService,
)
from catchup.sync.repair.context import RecordRepairContext

CHANNEL_ID = "channel-123"
SPACE_ID = "space-123"
SYNC_FROM = datetime(2026, 5, 1, tzinfo=timezone.utc)


class _FakeRepository:
    def __init__(self) -> None:
        self.user_chat_ids = ["chat-1"]
        self.article_ids = ["article-1"]

    async def list_channel_talk_user_chat_record_ids(self, *, channel_id, since):
        self.last_user_chat_args = (channel_id, since)
        return self.user_chat_ids

    async def list_channel_talk_document_article_record_ids(
        self,
        *,
        channel_id,
        space_id,
        since,
    ):
        self.last_article_args = (channel_id, space_id, since)
        return self.article_ids


class _FakeUserChatFetcher:
    async def fetch_user_chats(self, *, connection, states, sync_window):
        self.last_call = (connection, states, sync_window)
        return SimpleNamespace(
            bundles=[
                SimpleNamespace(detail=SimpleNamespace(user_chat_id="chat-1")),
                SimpleNamespace(detail=SimpleNamespace(user_chat_id="chat-2")),
            ],
        )


class _FakeArticleFetcher:
    async def fetch_articles(self, *, connection, language, sync_window, states):
        self.last_call = (connection, language, sync_window, states)
        return SimpleNamespace(article_ids=("article-1", "article-2"))


class _FakeUserChatIncrementalAdapter:
    async def sync_user_chat_by_id(self, *, execution, user_chat_id, sync_window):
        self.last_call = (execution, user_chat_id, sync_window)
        return SimpleNamespace(persisted_count=1)


class _FakeArticleIncrementalAdapter:
    async def sync_article_by_id(self, *, execution, article_id, sync_window):
        self.last_call = (execution, article_id, sync_window)
        return SimpleNamespace(persisted_count=1)


def _channel_connection() -> ChannelTalkCredentialsRecord:
    return ChannelTalkCredentialsRecord(
        channel_id=CHANNEL_ID,
        channel_name="Support",
        access_key="access-key",
        access_secret="access-secret",
        webhook_token="webhook-token",
    )


def _document_connection() -> ChannelTalkDocumentCredentialsRecord:
    return ChannelTalkDocumentCredentialsRecord(
        channel_id=CHANNEL_ID,
        space_id=SPACE_ID,
        space_name="Help Center",
        access_key="documents-access-key",
        access_secret="documents-access-secret",
        association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
    )


def _context(
    *,
    target_type: SyncTargetType,
    target_id: str,
    target_name: str,
) -> RecordRepairContext:
    return RecordRepairContext(
        event_id="event-123",
        attempt=1,
        event_status=SyncEventStatus.FAILED,
        connector=SyncConnector.CHANNEL_TALK,
        scope_id=CHANNEL_ID,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        sync_from_ts=str(SYNC_FROM.timestamp()),
        sync_from_dt=SYNC_FROM,
    )


class ChannelTalkRecordRepairServiceTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.repository = _FakeRepository()
        self.service = ChannelTalkRecordRepairService(
            repository=self.repository,
            user_chat_fetcher=_FakeUserChatFetcher(),
            article_fetcher=_FakeArticleFetcher(),
            user_chat_incremental_adapter=_FakeUserChatIncrementalAdapter(),
            article_incremental_adapter=_FakeArticleIncrementalAdapter(),
        )

    async def test_get_record_gaps_for_channel_talk_channel_reports_user_chats(self) -> None:
        context = _context(
            target_type=SyncTargetType.CHANNEL,
            target_id=CHANNEL_ID,
            target_name="Support",
        )

        with patch(
            "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_connection",
            return_value=_channel_connection(),
        ):
            response = await self.service.get_record_gaps(repair_context=context)

        self.assertEqual(response.connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(response.target_name, "Support")
        self.assertEqual(len(response.records), 1)
        self.assertEqual(response.records[0].record_type, CHANNEL_TALK_USER_CHAT_RECORD_TYPE)
        self.assertEqual(response.records[0].expected_count, 2)
        self.assertEqual(response.records[0].stored_count, 1)
        self.assertEqual(response.records[0].missing_count, 1)
        self.assertEqual(response.records[0].missing_ids, ["chat-2"])
        self.assertEqual(self.repository.last_user_chat_args, (CHANNEL_ID, SYNC_FROM))

    async def test_get_record_gaps_for_channel_talk_space_reports_articles(self) -> None:
        context = _context(
            target_type=SyncTargetType.SPACE,
            target_id=SPACE_ID,
            target_name="Help Center",
        )

        with (
            patch(
                "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_connection",
                return_value=_channel_connection(),
            ),
            patch(
                "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_document_connection",
                return_value=_document_connection(),
            ),
        ):
            response = await self.service.get_record_gaps(repair_context=context)

        self.assertEqual(response.connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(response.target_name, "Help Center")
        self.assertEqual(len(response.records), 1)
        self.assertEqual(
            response.records[0].record_type,
            CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE,
        )
        self.assertEqual(response.records[0].expected_count, 2)
        self.assertEqual(response.records[0].stored_count, 1)
        self.assertEqual(response.records[0].missing_count, 1)
        self.assertEqual(response.records[0].missing_ids, ["article-2"])
        self.assertEqual(
            self.repository.last_article_args,
            (CHANNEL_ID, SPACE_ID, SYNC_FROM),
        )

    async def test_retry_user_chat_rechecks_remaining_missing_ids(self) -> None:
        context = _context(
            target_type=SyncTargetType.CHANNEL,
            target_id=CHANNEL_ID,
            target_name="Support",
        )
        self.repository.user_chat_ids = ["chat-1", "chat-2"]

        with patch(
            "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_connection",
            return_value=_channel_connection(),
        ):
            response = await self.service.retry_records(
                request=SyncRecordRetryRequest(
                    event_id="event-123",
                    records=[
                        SyncRecordRetryItemRequest(
                            record_type=CHANNEL_TALK_USER_CHAT_RECORD_TYPE,
                            record_ids=["chat-2"],
                        )
                    ],
                ),
                repair_context=context,
            )

        self.assertEqual(len(response.records), 1)
        self.assertEqual(response.records[0].record_type, CHANNEL_TALK_USER_CHAT_RECORD_TYPE)
        self.assertEqual(response.records[0].retried_count, 1)
        self.assertEqual(response.records[0].succeeded_count, 1)
        self.assertEqual(response.records[0].remaining_missing_ids, [])

    async def test_retry_document_article_rechecks_remaining_missing_ids(self) -> None:
        context = _context(
            target_type=SyncTargetType.SPACE,
            target_id=SPACE_ID,
            target_name="Help Center",
        )
        self.repository.article_ids = ["article-1", "article-2"]

        with (
            patch(
                "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_connection",
                return_value=_channel_connection(),
            ),
            patch(
                "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_document_connection",
                return_value=_document_connection(),
            ),
        ):
            response = await self.service.retry_records(
                request=SyncRecordRetryRequest(
                    event_id="event-123",
                    records=[
                        SyncRecordRetryItemRequest(
                            record_type=CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE,
                            record_ids=["article-2"],
                        )
                    ],
                ),
                repair_context=context,
            )

        self.assertEqual(len(response.records), 1)
        self.assertEqual(
            response.records[0].record_type,
            CHANNEL_TALK_DOCUMENT_ARTICLE_RECORD_TYPE,
        )
        self.assertEqual(response.records[0].retried_count, 1)
        self.assertEqual(response.records[0].succeeded_count, 1)
        self.assertEqual(response.records[0].remaining_missing_ids, [])

    async def test_retry_rejects_user_chat_record_for_space_target(self) -> None:
        context = _context(
            target_type=SyncTargetType.SPACE,
            target_id=SPACE_ID,
            target_name="Help Center",
        )

        with (
            patch(
                "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_connection",
                return_value=_channel_connection(),
            ),
            patch(
                "catchup.sync.repair.channel_talk_record_repair_service.load_channel_talk_document_connection",
                return_value=_document_connection(),
            ),
            self.assertRaises(SyncRequestException) as raised,
        ):
            await self.service.retry_records(
                request=SyncRecordRetryRequest(
                    event_id="event-123",
                    records=[
                        SyncRecordRetryItemRequest(
                            record_type=CHANNEL_TALK_USER_CHAT_RECORD_TYPE,
                            record_ids=["chat-1"],
                        )
                    ],
                ),
                repair_context=context,
            )

        self.assertEqual(raised.exception.code, "unsupported_record_type")
