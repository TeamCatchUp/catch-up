from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkChannelMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkCurrentChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadataPage
from catchup.connectors.channel_talk.schemas import ChannelTalkMetadataSyncRequest
from catchup.connectors.channel_talk.service import ChannelTalkMetadataSyncService


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class ChannelTalkMetadataSchemaTests(IsolatedAsyncioTestCase):
    async def test_manager_group_and_user_payloads_are_normalized(self) -> None:
        manager_page = ChannelTalkManagerMetadataPage.from_api_payload(
            {
                "next": "next@example.com",
                "managers": [
                    {
                        "id": "manager-1",
                        "channelId": "channel-123",
                        "name": "Kim",
                        "email": "kim@example.com",
                        "roleId": "role-1",
                        "displayAsChannel": True,
                        "createdAt": 1713492788000,
                    }
                ],
            }
        )
        group = ChannelTalkGroupMetadata.from_api_payload(
            {
                "id": "group-1",
                "channelId": "channel-123",
                "name": "VIP",
                "managerIds": ["manager-1", "manager-2"],
                "createdAt": 1713492788000,
                "updatedAt": 1713492799000,
            }
        )
        # role_id alias를 추가한 뒤에도 manager payload 정규화 결과가 그대로 읽히는지 잠근다.
        self.assertEqual(manager_page.next_page_token, "next@example.com")
        self.assertEqual(manager_page.managers[0].manager_id, "manager-1")
        self.assertEqual(manager_page.managers[0].role_id, "role-1")
        self.assertTrue(manager_page.managers[0].display_as_channel)
        self.assertEqual(group.group_id, "group-1")
        self.assertEqual(group.manager_ids, ("manager-1", "manager-2"))
        self.assertEqual(len(group.to_memberships("channel-123")), 2)


class ChannelTalkMetadataSyncServiceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = SimpleNamespace(
            get_connection=lambda: ChannelTalkCredentialsRecord(
                channel_id="channel-123",
                channel_name="Support",
                access_key="access-key",
                access_secret="access-secret",
                webhook_token="webhook-token",
            ),
            upsert_channel_metadata=lambda payload: payload,
            bulk_upsert_managers=lambda payloads: payloads,
            bulk_upsert_groups=lambda payloads: payloads,
            replace_group_managers=lambda *, channel_id, memberships: memberships,
            commit=lambda: None,
        )
        self.client = SimpleNamespace(
            get_current_channel=None,
            list_managers=None,
            list_groups=None,
        )
        self.service = ChannelTalkMetadataSyncService(store=self.store, client=self.client)
        self.run_in_threadpool_patcher = patch(
            "catchup.connector_core.adapters.channel_talk.metadata_sync_adapter.run_in_threadpool",
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)

    async def test_sync_channel_uses_persisted_credentials_and_replaces_memberships(self) -> None:
        commits: list[str] = []
        persisted_channels: list[ChannelTalkChannelMetadata] = []
        persisted_manager_batches: list[list[str]] = []
        persisted_group_batches: list[list[str]] = []
        replaced_memberships: list[tuple[str, str, str]] = []
        manager_calls: list[str | None] = []
        group_calls: list[str | None] = []

        self.store.commit = lambda: commits.append("commit")
        self.store.upsert_channel_metadata = lambda payload: persisted_channels.append(payload) or payload
        self.store.bulk_upsert_managers = (
            lambda payloads: persisted_manager_batches.append([item.manager_id for item in payloads]) or payloads
        )
        self.store.bulk_upsert_groups = (
            lambda payloads: persisted_group_batches.append([item.group_id for item in payloads]) or payloads
        )

        def replace_group_managers(*, channel_id, memberships):
            replaced_memberships.extend(
                (item.channel_id, item.group_id, item.manager_id) for item in memberships
            )
            return memberships

        self.store.replace_group_managers = replace_group_managers

        async def get_current_channel(*, access_key: str, access_secret: str):
            self.assertEqual(access_key, "access-key")
            self.assertEqual(access_secret, "access-secret")
            return ChannelTalkCurrentChannel(
                channel=ChannelTalkChannel(
                    channel_id="channel-123",
                    channel_name="Support",
                )
            )

        async def list_managers(*, access_key: str, access_secret: str, since: str | None = None):
            manager_calls.append(since)
            if since is None:
                return ChannelTalkManagerMetadataPage.from_api_payload(
                    {
                        "next": "kim@example.com",
                        "managers": [
                            {"id": "manager-1", "name": "Kim", "email": "kim@example.com"},
                        ],
                    }
                )
            return ChannelTalkManagerMetadataPage.from_api_payload(
                {
                    "managers": [
                        {"id": "manager-2", "name": "Park", "email": "park@example.com"},
                    ]
                }
            )

        async def list_groups(*, access_key: str, access_secret: str, since: str | None = None):
            group_calls.append(since)
            return SimpleNamespace(
                groups=[
                    ChannelTalkGroupMetadata(
                        group_id="group-1",
                        group_name="VIP",
                        manager_ids=("manager-1", "manager-2"),
                    ),
                ],
                next_page_token=None,
            )

        self.client.get_current_channel = get_current_channel
        self.client.list_managers = list_managers
        self.client.list_groups = list_groups

        result = await self.service.sync_metadata(
            ChannelTalkMetadataSyncRequest(channel_id="channel-123")
        )

        self.assertEqual([item.channel_id for item in persisted_channels], ["channel-123"])
        self.assertEqual(persisted_manager_batches, [["manager-1"], ["manager-2"]])
        self.assertEqual(persisted_group_batches, [["group-1"]])
        self.assertEqual(
            replaced_memberships,
            [
                ("channel-123", "group-1", "manager-1"),
                ("channel-123", "group-1", "manager-2"),
            ],
        )
        self.assertEqual(manager_calls, [None, "kim@example.com"])
        self.assertEqual(group_calls, [None])
        # channel, managers(page1/page2), groups, group-memberships까지 stage별 commit을 남긴다.
        self.assertEqual(commits, ["commit", "commit", "commit", "commit", "commit"])
        self.assertEqual(result.connector, ConnectorKey.CHANNEL_TALK)
        self.assertTrue(result.channel_synced)
        self.assertEqual(result.managers_synced, 2)
        self.assertEqual(result.groups_synced, 1)
        self.assertEqual(result.group_manager_links_synced, 2)

    async def test_sync_channel_requires_installed_credentials(self) -> None:
        self.store.get_connection = lambda: None

        # 설치되지 않은 credential은 sync 시작 전에 바로 막혀야 한다.
        with self.assertRaisesRegex(
            ChannelTalkValidationError,
            "Channel Talk credentials are not installed",
        ):
            await self.service.sync_metadata(
                ChannelTalkMetadataSyncRequest(channel_id="channel-123")
            )

    async def test_sync_channel_rejects_requested_channel_mismatch(self) -> None:
        self.store.get_connection = lambda: ChannelTalkCredentialsRecord(
            channel_id="channel-999",
            channel_name="Other",
            access_key="access-key",
            access_secret="access-secret",
            webhook_token="webhook-token",
        )

        # 다른 채널 credential 재사용으로 cross-tenant write가 나지 않게 mismatch를 고정한다.
        with self.assertRaisesRegex(
            ChannelTalkConflictError,
            "Stored Channel Talk credentials do not match the requested channel",
        ):
            await self.service.sync_metadata(
                ChannelTalkMetadataSyncRequest(channel_id="channel-123")
            )
