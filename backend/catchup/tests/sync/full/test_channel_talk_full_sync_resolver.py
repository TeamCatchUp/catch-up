from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import patch

from catchup.connectors.channel_talk.full_sync_helper import (
    CHANNEL_TALK_FULL_SYNC_TARGET_ID,
)
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.db.models import SyncConnector
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.full.registry import get_full_sync_target_resolver
from catchup.sync.full.registry import list_registered_sync_connectors
from catchup.sync.full.resolvers.channel_talk_full_sync_resolver import (
    ChannelTalkFullSyncTargetResolver,
)

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


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class ChannelTalkFullSyncResolverTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.resolver = ChannelTalkFullSyncTargetResolver()
        self.run_in_threadpool_patcher = patch(
            "catchup.sync.full.resolvers.channel_talk_full_sync_resolver.run_in_threadpool",
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_resolver_returns_exact_user_chat_singleton_target(self) -> None:
        with patch(
            "catchup.sync.full.resolvers.channel_talk_full_sync_resolver.load_channel_talk_connection",
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
            CHANNEL_TALK_FULL_SYNC_TARGET_ID,
        )
        self.assertEqual(result.targets[0].target_type.value, "resource")
        self.assertEqual(result.targets[0].metadata, {})

    async def test_resolver_rejects_unknown_target_ids(self) -> None:
        with patch(
            "catchup.sync.full.resolvers.channel_talk_full_sync_resolver.load_channel_talk_connection",
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
            "catchup.sync.full.resolvers.channel_talk_full_sync_resolver.load_channel_talk_connection",
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
            "catchup.sync.full.resolvers.channel_talk_full_sync_resolver.load_channel_talk_connection",
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
