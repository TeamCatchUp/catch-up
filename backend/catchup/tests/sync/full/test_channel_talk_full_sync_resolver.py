from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
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
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.db.models import SyncConnector
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.full.registry import get_full_sync_target_resolver
from catchup.sync.full.registry import list_registered_sync_connectors
from catchup.sync.full.resolvers.channel_talk_full_sync_resolver import (
    ChannelTalkFullSyncTargetResolver,
)

CHANNEL_ID = "channel-123"
_RESOLVER_MODULE = "catchup.sync.full.resolvers.channel_talk_full_sync_resolver"
_LOAD_CONNECTION = f"{_RESOLVER_MODULE}.load_channel_talk_connection"
_LOAD_DOCUMENT_CONNECTION = f"{_RESOLVER_MODULE}.load_channel_talk_document_connection"
_RUN_IN_THREADPOOL = f"{_RESOLVER_MODULE}.run_in_threadpool"


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


class ChannelTalkFullSyncResolverTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.resolver = ChannelTalkFullSyncTargetResolver()
        self.run_in_threadpool_patcher = patch(
            _RUN_IN_THREADPOOL,
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_resolver_returns_exact_user_chat_singleton_target(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    target_ids=[CHANNEL_TALK_FULL_SYNC_TARGET_ID],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(len(result.targets), 1)
        self.assertEqual(
            result.targets[0].target_id,
            CHANNEL_TALK_FULL_SYNC_TARGET_ID,
        )
        self.assertEqual(
            result.targets[0].target_name,
            "UserChat",
        )
        self.assertEqual(result.targets[0].target_type.value, "resource")
        self.assertEqual(
            result.targets[0].metadata,
            {
                "runtime_target_kind": "bootstrap",
                "boundary": "tenant",
                "target": CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                "stage": CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                "channel_id": CHANNEL_ID,
            },
        )

    async def test_resolver_rejects_unknown_target_ids(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "requested target_ids contain unknown channel_talk targets",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        target_ids=["group"],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_document_article_when_documents_not_connected(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=None,
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk documents is not connected for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        target_ids=[CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_returns_document_article_when_documents_connected(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=_build_document_connection_record(),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    target_ids=[CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(len(result.targets), 1)
        self.assertEqual(
            result.targets[0].target_id,
            CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
        )
        self.assertEqual(result.targets[0].target_name, "DocumentArticle")
        self.assertEqual(
            result.targets[0].metadata,
            {
                "runtime_target_kind": "bootstrap",
                "boundary": "tenant",
                "target": CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
                "stage": CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
                "channel_id": CHANNEL_ID,
                "space_id": "space-123",
                "space_name": "Help Center",
            },
        )

    async def test_resolver_rejects_document_article_when_documents_channel_mismatches(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=_build_document_connection_record(channel_id="channel-other"),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk documents is not connected for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        target_ids=[CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_document_article_when_documents_unverified(
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
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk documents is not connected for the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        target_ids=[CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_returns_mixed_document_article_request(
        self,
    ) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(),
        ), patch(
            _LOAD_DOCUMENT_CONNECTION,
            return_value=_build_document_connection_record(),
        ):
            result = await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id=CHANNEL_ID,
                    target_ids=[
                        CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                        CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
                    ],
                    sync_from_ts="1713744000.000000",
                ),
            )

        self.assertEqual(
            [target.target_id for target in result.targets],
            [
                CHANNEL_TALK_FULL_SYNC_TARGET_ID,
                CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
            ],
        )

    async def test_resolver_rejects_blank_scope_id(self) -> None:
        with self.assertRaisesRegex(
            SyncRequestException,
            "scope_id is required",
        ):
            await self.resolver.resolve_full_sync_targets(
                request=FullSyncDispatchRequest(
                    scope_id="",
                    target_ids=[CHANNEL_TALK_FULL_SYNC_TARGET_ID],
                    sync_from_ts="1713744000.000000",
                ),
            )

    async def test_resolver_rejects_missing_channel_talk_connection(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=None,
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "channel_talk is not connected",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        target_ids=[CHANNEL_TALK_FULL_SYNC_TARGET_ID],
                        sync_from_ts="1713744000.000000",
                    ),
                )

    async def test_resolver_rejects_requested_channel_mismatch(self) -> None:
        with patch(
            _LOAD_CONNECTION,
            return_value=_build_connection_record(channel_id="channel-other"),
        ):
            with self.assertRaisesRegex(
                SyncRequestException,
                "Stored Channel Talk credentials do not match the requested channel",
            ):
                await self.resolver.resolve_full_sync_targets(
                    request=FullSyncDispatchRequest(
                        scope_id=CHANNEL_ID,
                        target_ids=[CHANNEL_TALK_FULL_SYNC_TARGET_ID],
                        sync_from_ts="1713744000.000000",
                    ),
                )


class FullSyncRegistryAdmissionTests(TestCase):
    def test_registry_includes_channel_talk_without_dropping_existing_connectors(self) -> None:
        registered = set(list_registered_sync_connectors())

        self.assertEqual(
            registered,
            {
                SyncConnector.SLACK,
                SyncConnector.GITHUB,
                SyncConnector.JIRA,
                SyncConnector.CONFLUENCE,
                SyncConnector.CHANNEL_TALK,
            },
        )
        self.assertIsNotNone(
            get_full_sync_target_resolver(SyncConnector.CHANNEL_TALK),
        )
