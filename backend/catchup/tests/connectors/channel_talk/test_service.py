from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkManager
from catchup.connectors.channel_talk.service import ChannelTalkCredentialsService


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class ChannelTalkCredentialsServiceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = SimpleNamespace(
            get_connection=lambda: None,
            list_connections=lambda: [],
            upsert_connection=lambda payload: payload.to_record(),
            delete_connection=lambda channel_id=None: False,
            commit=lambda: None,
        )
        self.client = SimpleNamespace(
            get_current_channel=None,
        )
        self.service = ChannelTalkCredentialsService(store=self.store, client=self.client)
        self.run_in_threadpool_patcher = patch(
            "catchup.connectors.channel_talk.install_auth_adapter.run_in_threadpool",
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_connect_validates_persists_and_returns_status(self) -> None:
        verified_channel = ChannelTalkCurrentChannel(
            channel=ChannelTalkChannel(id="channel-123", name="Support"),
            manager=ChannelTalkManager(id="manager-7", name="Jane"),
        )
        stored_records: list[ChannelTalkCredentialsRecord] = []
        commits: list[str] = []

        async def get_current_channel(*, access_key: str, access_secret: str):
            self.assertEqual(access_key, "access-key")
            self.assertEqual(access_secret, "access-secret")
            return verified_channel

        def upsert_connection(payload):
            stored_records.append(payload.to_record())
            return stored_records[-1]

        def commit():
            commits.append("commit")

        self.client.get_current_channel = get_current_channel
        self.store.upsert_connection = upsert_connection
        self.store.commit = commit

        before = datetime.now(timezone.utc)
        result = await self.service.connect(
            ChannelTalkConnectRequest(
                access_key="access-key",
                access_secret="access-secret",
                webhook_token="webhook-token",
            )
        )
        after = datetime.now(timezone.utc)

        self.assertTrue(result.installed)
        self.assertEqual(result.channel_id, "channel-123")
        self.assertEqual(result.channel_name, "Support")
        self.assertTrue(result.webhook_token_configured)
        self.assertEqual(commits, ["commit"])
        self.assertEqual(len(stored_records), 1)
        self.assertEqual(stored_records[0].channel_id, "channel-123")
        self.assertEqual(stored_records[0].channel_name, "Support")
        self.assertEqual(stored_records[0].access_key, "access-key")
        self.assertEqual(stored_records[0].access_secret, "access-secret")
        self.assertEqual(stored_records[0].webhook_token, "webhook-token")
        self.assertIsNotNone(stored_records[0].credential_last_verified_at)
        self.assertGreaterEqual(stored_records[0].credential_last_verified_at, before)
        self.assertLessEqual(stored_records[0].credential_last_verified_at, after)

    async def test_get_status_returns_disconnected_when_store_is_empty(self) -> None:
        self.store.get_connection = lambda: None

        result = await self.service.get_status()

        self.assertFalse(result.installed)
        self.assertIsNone(result.channel_id)
        self.assertFalse(result.webhook_token_configured)

    async def test_list_statuses_returns_all_store_connections(self) -> None:
        verified_at = datetime(2026, 4, 19, 8, 30, tzinfo=timezone.utc)
        self.store.list_connections = lambda: [
            ChannelTalkCredentialsRecord(
                channel_id="channel-123",
                channel_name="Support",
                credential_last_verified_at=verified_at,
                webhook_token="webhook-token",
            ),
            ChannelTalkCredentialsRecord(
                channel_id="channel-456",
                channel_name="Sales",
                credential_last_verified_at=verified_at,
            ),
        ]

        result = await self.service.list_statuses()

        self.assertEqual([item.channel_id for item in result], ["channel-123", "channel-456"])
        self.assertTrue(result[0].webhook_token_configured)
        self.assertFalse(result[1].webhook_token_configured)

    async def test_uninstall_deletes_by_channel_id_and_commits_even_when_nothing_was_removed(self) -> None:
        commits: list[str] = []
        deleted_channel_ids: list[str] = []

        def delete_connection(channel_id=None):
            deleted_channel_ids.append(channel_id)
            return False

        self.store.delete_connection = delete_connection
        self.store.commit = lambda: commits.append("commit")

        result = await self.service.uninstall("channel-123")

        self.assertFalse(result.removed)
        self.assertFalse(result.installed)
        self.assertEqual(deleted_channel_ids, ["channel-123"])
        self.assertEqual(commits, ["commit"])
