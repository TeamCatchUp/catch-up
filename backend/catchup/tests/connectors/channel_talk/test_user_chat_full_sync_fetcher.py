from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadataPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessagePage,
)
from catchup.sync.ingestion.schemas import SyncWindow


def _window() -> SyncWindow:
    return SyncWindow(
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
    )


def _connection() -> ChannelTalkUserChatFullSyncConnection:
    return ChannelTalkUserChatFullSyncConnection.from_credentials_record(
        ChannelTalkCredentialsRecord(
            channel_id="channel-123",
            channel_name="Support",
            access_key="access-key",
            access_secret="access-secret",
            webhook_token="webhook-token",
        )
    )


def _list_item(
    *,
    user_chat_id: str,
    state: ChannelTalkUserChatState,
    ordering_marker: datetime,
) -> ChannelTalkUserChatListItem:
    return ChannelTalkUserChatListItem(
        user_chat_id=user_chat_id,
        state=state,
        ordering_marker=ordering_marker,
        user_id=f"user-{user_chat_id}",
        member_id=f"member-{user_chat_id}",
    )


def _detail(
    *,
    user_chat_id: str,
    state: ChannelTalkUserChatState,
) -> ChannelTalkUserChatDetail:
    return ChannelTalkUserChatDetail.from_api_payload(
        {
            "id": user_chat_id,
            "channelId": "channel-123",
            "state": state.value,
            "name": f"Conversation {user_chat_id}",
            "createdAt": "2026-04-21T09:00:00Z",
            "deskUpdatedAt": "2026-04-21T09:30:00Z",
            "user": {
                "id": f"user-{user_chat_id}",
                "memberId": f"member-{user_chat_id}",
                "name": "Customer Kim",
            },
        },
        user_chat_id=user_chat_id,
    )


def _message(
    *,
    message_id: str,
    user_chat_id: str,
    created_at: str,
) -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": message_id,
            "chatId": user_chat_id,
            "personType": "manager",
            "manager": {"id": "manager-1", "name": "Agent Lee"},
            "plainText": f"message:{message_id}",
            "createdAt": created_at,
        },
        user_chat_id=user_chat_id,
    )


class ChannelTalkUserChatFullSyncFetcherTests(IsolatedAsyncioTestCase):
    async def test_fetch_managers_by_id_loads_once_per_full_sync_run(self) -> None:
        client = SimpleNamespace(
            list_managers=AsyncMock(
                side_effect=[
                    ChannelTalkManagerMetadataPage(
                        managers=[
                            ChannelTalkManagerMetadata(
                                manager_id="manager-1",
                                name="Agent Lee",
                            )
                        ],
                        next_page_token="manager-page-2",
                    ),
                    ChannelTalkManagerMetadataPage(
                        managers=[
                            ChannelTalkManagerMetadata(
                                manager_id="manager-2",
                                name="Agent Park",
                            )
                        ],
                        next_page_token=None,
                    ),
                ]
            )
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(client=client)

        managers_by_id = await fetcher.fetch_managers_by_id(
            connection=_connection(),
        )

        self.assertEqual(list(managers_by_id), ["manager-1", "manager-2"])
        self.assertEqual(managers_by_id["manager-2"].name, "Agent Park")
        self.assertEqual(client.list_managers.await_count, 2)
        self.assertEqual(
            [call.kwargs["channel_id"] for call in client.list_managers.await_args_list],
            ["channel-123", "channel-123"],
        )
        self.assertEqual(
            [call.kwargs["since"] for call in client.list_managers.await_args_list],
            [None, "manager-page-2"],
        )

    async def test_fetch_user_chats_resumes_from_checkpoint_state_and_cursor(self) -> None:
        recent_item = _list_item(
            user_chat_id="chat-recent",
            state=ChannelTalkUserChatState.CLOSED,
            ordering_marker=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        )
        old_item = _list_item(
            user_chat_id="chat-old",
            state=ChannelTalkUserChatState.CLOSED,
            ordering_marker=datetime(2026, 4, 20, 23, 59, tzinfo=timezone.utc),
        )
        client = SimpleNamespace(
            list_user_chats=AsyncMock(
                side_effect=[
                    ChannelTalkUserChatListPage(
                        items=[recent_item, old_item],
                        next_cursor="chat-page-2",
                    ),
                    ChannelTalkUserChatListPage(items=[], next_cursor=None),
                ]
            ),
            get_user_chat=AsyncMock(return_value=_detail(
                user_chat_id="chat-recent",
                state=ChannelTalkUserChatState.CLOSED,
            )),
            list_user_chat_messages=AsyncMock(
                side_effect=[
                    ChannelTalkUserChatMessagePage(
                        messages=[
                            _message(
                                message_id="msg-1",
                                user_chat_id="chat-recent",
                                created_at="2026-04-21T09:00:00Z",
                            )
                        ],
                        next_cursor="message-page-2",
                    ),
                    ChannelTalkUserChatMessagePage(
                        messages=[
                            _message(
                                message_id="msg-2",
                                user_chat_id="chat-recent",
                                created_at="2026-04-21T09:05:00Z",
                            )
                        ],
                        next_cursor=None,
                    ),
                ]
            ),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(client=client)

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
                ChannelTalkUserChatState.SNOOZED,
            ),
            sync_window=_window(),
            checkpoint_state=ChannelTalkUserChatState.CLOSED,
            checkpoint_cursor="cursor-1",
        )
        bundles = result.bundles

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].state, ChannelTalkUserChatState.CLOSED)
        self.assertEqual(bundles[0].detail.user_chat_id, "chat-recent")
        self.assertEqual(
            [message.message_id for message in bundles[0].messages],
            ["msg-1", "msg-2"],
        )
        self.assertEqual(client.list_user_chats.await_count, 2)
        self.assertEqual(
            [call.kwargs["state"] for call in client.list_user_chats.await_args_list],
            [
                ChannelTalkUserChatState.CLOSED,
                ChannelTalkUserChatState.SNOOZED,
            ],
        )
        self.assertEqual(
            [call.kwargs["since"] for call in client.list_user_chats.await_args_list],
            ["cursor-1", None],
        )
        self.assertEqual(
            [call.kwargs["channel_id"] for call in client.list_user_chats.await_args_list],
            ["channel-123", "channel-123"],
        )
        client.get_user_chat.assert_awaited_once_with(
            access_key="access-key",
            access_secret="access-secret",
            channel_id="channel-123",
            user_chat_id="chat-recent",
        )
        self.assertEqual(client.list_user_chat_messages.await_count, 2)
        first_message_call = client.list_user_chat_messages.await_args_list[0]
        second_message_call = client.list_user_chat_messages.await_args_list[1]
        self.assertEqual(first_message_call.kwargs["channel_id"], "channel-123")
        self.assertEqual(second_message_call.kwargs["channel_id"], "channel-123")
        self.assertEqual(first_message_call.kwargs["since"], None)
        self.assertEqual(second_message_call.kwargs["since"], "message-page-2")

    async def test_fetch_user_chats_sweeps_states_and_continues_pagination_without_checkpoint(
        self,
    ) -> None:
        opened_page_1 = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-opened-1",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
                )
            ],
            next_cursor="opened-page-2",
        )
        opened_page_2 = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-opened-2",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 10, 30, tzinfo=timezone.utc),
                )
            ],
            next_cursor=None,
        )
        closed_page = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-closed-1",
                    state=ChannelTalkUserChatState.CLOSED,
                    ordering_marker=datetime(2026, 4, 21, 10, 15, tzinfo=timezone.utc),
                )
            ],
            next_cursor=None,
        )
        client = SimpleNamespace(
            list_user_chats=AsyncMock(
                side_effect=[opened_page_1, opened_page_2, closed_page]
            ),
            get_user_chat=AsyncMock(
                side_effect=[
                    _detail(
                        user_chat_id="chat-opened-1",
                        state=ChannelTalkUserChatState.OPENED,
                    ),
                    _detail(
                        user_chat_id="chat-opened-2",
                        state=ChannelTalkUserChatState.OPENED,
                    ),
                    _detail(
                        user_chat_id="chat-closed-1",
                        state=ChannelTalkUserChatState.CLOSED,
                    ),
                ]
            ),
            list_user_chat_messages=AsyncMock(
                side_effect=[
                    ChannelTalkUserChatMessagePage(
                        messages=[
                            _message(
                                message_id="msg-opened-1",
                                user_chat_id="chat-opened-1",
                                created_at="2026-04-21T11:00:00Z",
                            )
                        ]
                    ),
                    ChannelTalkUserChatMessagePage(
                        messages=[
                            _message(
                                message_id="msg-opened-2",
                                user_chat_id="chat-opened-2",
                                created_at="2026-04-21T10:30:00Z",
                            )
                        ]
                    ),
                    ChannelTalkUserChatMessagePage(
                        messages=[
                            _message(
                                message_id="msg-closed-1",
                                user_chat_id="chat-closed-1",
                                created_at="2026-04-21T10:15:00Z",
                            )
                        ]
                    ),
                ]
            ),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(client=client)

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
            ),
            sync_window=_window(),
        )
        bundles = result.bundles

        self.assertEqual(
            [bundle.detail.user_chat_id for bundle in bundles],
            ["chat-opened-1", "chat-opened-2", "chat-closed-1"],
        )
        self.assertEqual(client.list_user_chats.await_count, 3)
        self.assertEqual(
            [call.kwargs["state"] for call in client.list_user_chats.await_args_list],
            [
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
            ],
        )
        self.assertEqual(
            [call.kwargs["since"] for call in client.list_user_chats.await_args_list],
            [None, "opened-page-2", None],
        )
        self.assertEqual(
            [call.kwargs["channel_id"] for call in client.list_user_chats.await_args_list],
            ["channel-123", "channel-123", "channel-123"],
        )

    async def test_fetch_user_chats_stops_current_state_when_desc_page_reaches_window_start(
        self,
    ) -> None:
        page = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-recent",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
                ),
                _list_item(
                    user_chat_id="chat-old",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 20, 23, 59, tzinfo=timezone.utc),
                ),
                _list_item(
                    user_chat_id="chat-after-old",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
                ),
            ],
            next_cursor="opened-page-2",
        )
        client = SimpleNamespace(
            list_user_chats=AsyncMock(return_value=page),
            get_user_chat=AsyncMock(
                return_value=_detail(
                    user_chat_id="chat-recent",
                    state=ChannelTalkUserChatState.OPENED,
                )
            ),
            list_user_chat_messages=AsyncMock(
                return_value=ChannelTalkUserChatMessagePage(messages=[])
            ),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(client=client)

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(ChannelTalkUserChatState.OPENED,),
            sync_window=_window(),
        )
        bundles = result.bundles

        self.assertEqual([bundle.detail.user_chat_id for bundle in bundles], ["chat-recent"])
        client.get_user_chat.assert_awaited_once()
        self.assertEqual(client.list_user_chats.await_count, 1)

    async def test_fetch_user_chats_skips_records_newer_than_window_end(self) -> None:
        page = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-future",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 23, 0, 1, tzinfo=timezone.utc),
                ),
                _list_item(
                    user_chat_id="chat-current",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
                ),
            ],
            next_cursor=None,
        )
        client = SimpleNamespace(
            list_user_chats=AsyncMock(return_value=page),
            get_user_chat=AsyncMock(
                return_value=_detail(
                    user_chat_id="chat-current",
                    state=ChannelTalkUserChatState.OPENED,
                )
            ),
            list_user_chat_messages=AsyncMock(
                return_value=ChannelTalkUserChatMessagePage(messages=[])
            ),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(client=client)

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(ChannelTalkUserChatState.OPENED,),
            sync_window=_window(),
        )

        self.assertEqual(
            [bundle.detail.user_chat_id for bundle in result.bundles],
            ["chat-current"],
        )
        client.get_user_chat.assert_awaited_once_with(
            access_key="access-key",
            access_secret="access-secret",
            channel_id="channel-123",
            user_chat_id="chat-current",
        )

    async def test_fetch_user_chats_emits_next_checkpoint_when_page_budget_is_reached(
        self,
    ) -> None:
        page = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-1",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
                ),
            ],
            next_cursor="opened-page-2",
        )
        client = SimpleNamespace(
            list_user_chats=AsyncMock(return_value=page),
            get_user_chat=AsyncMock(
                return_value=_detail(
                    user_chat_id="chat-1",
                    state=ChannelTalkUserChatState.OPENED,
                )
            ),
            list_user_chat_messages=AsyncMock(
                return_value=ChannelTalkUserChatMessagePage(messages=[])
            ),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(
            client=client,
            max_user_chat_pages_per_run=1,
        )

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(ChannelTalkUserChatState.OPENED,),
            sync_window=_window(),
        )

        self.assertEqual(
            [bundle.detail.user_chat_id for bundle in result.bundles],
            ["chat-1"],
        )
        self.assertEqual(result.next_checkpoint_state, ChannelTalkUserChatState.OPENED)
        self.assertEqual(result.next_checkpoint_cursor, "opened-page-2")

    async def test_fetch_user_chats_passes_configured_list_limit(self) -> None:
        page = ChannelTalkUserChatListPage(items=[], next_cursor=None)
        client = SimpleNamespace(
            list_user_chats=AsyncMock(return_value=page),
            get_user_chat=AsyncMock(),
            list_user_chat_messages=AsyncMock(),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(
            client=client,
            user_chat_list_limit=50,
        )

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(ChannelTalkUserChatState.OPENED,),
            sync_window=_window(),
        )

        self.assertEqual(result.bundles, ())
        client.list_user_chats.assert_awaited_once()
        self.assertEqual(client.list_user_chats.await_args.kwargs["limit"], 50)

    async def test_fetch_user_chats_omits_list_limit_when_unconfigured(self) -> None:
        page = ChannelTalkUserChatListPage(items=[], next_cursor=None)
        client = SimpleNamespace(
            list_user_chats=AsyncMock(return_value=page),
            get_user_chat=AsyncMock(),
            list_user_chat_messages=AsyncMock(),
        )
        fetcher = ChannelTalkUserChatFullSyncFetcher(client=client)

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(ChannelTalkUserChatState.OPENED,),
            sync_window=_window(),
        )

        self.assertEqual(result.bundles, ())
        client.list_user_chats.assert_awaited_once()
        self.assertNotIn("limit", client.list_user_chats.await_args.kwargs)

    async def test_fetch_user_chats_fetches_page_details_with_bounded_concurrency(
        self,
    ) -> None:
        page = ChannelTalkUserChatListPage(
            items=[
                _list_item(
                    user_chat_id="chat-1",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
                ),
                _list_item(
                    user_chat_id="chat-2",
                    state=ChannelTalkUserChatState.OPENED,
                    ordering_marker=datetime(2026, 4, 21, 9, 0, tzinfo=timezone.utc),
                ),
            ],
            next_cursor=None,
        )

        class ConcurrentClient:
            def __init__(self) -> None:
                self.list_user_chats = AsyncMock(return_value=page)
                self.inflight_detail_calls = 0
                self.max_inflight_detail_calls = 0

            async def get_user_chat(
                self,
                *,
                access_key: str,
                access_secret: str,
                channel_id: str,
                user_chat_id: str,
            ) -> ChannelTalkUserChatDetail:
                _ = access_key
                _ = access_secret
                _ = channel_id
                self.inflight_detail_calls += 1
                self.max_inflight_detail_calls = max(
                    self.max_inflight_detail_calls,
                    self.inflight_detail_calls,
                )
                await asyncio.sleep(0)
                self.inflight_detail_calls -= 1
                return _detail(
                    user_chat_id=user_chat_id,
                    state=ChannelTalkUserChatState.OPENED,
                )

            async def list_user_chat_messages(
                self,
                *,
                access_key: str,
                access_secret: str,
                channel_id: str,
                user_chat_id: str,
                since: str | None,
                sort_order: str,
            ) -> ChannelTalkUserChatMessagePage:
                _ = access_key
                _ = access_secret
                _ = channel_id
                _ = user_chat_id
                _ = since
                _ = sort_order
                await asyncio.sleep(0)
                return ChannelTalkUserChatMessagePage(messages=[])

        client = ConcurrentClient()
        fetcher = ChannelTalkUserChatFullSyncFetcher(
            client=client,
            max_concurrent_user_chat_fetches=2,
        )

        result = await fetcher.fetch_user_chats(
            connection=_connection(),
            states=(ChannelTalkUserChatState.OPENED,),
            sync_window=_window(),
        )
        bundles = result.bundles

        self.assertEqual([bundle.detail.user_chat_id for bundle in bundles], ["chat-1", "chat-2"])
        self.assertEqual(client.max_inflight_detail_calls, 2)
