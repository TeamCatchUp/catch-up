from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_original_fetcher import (
    ChannelTalkUserChatOriginalFetcher,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessagePage,
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


def _detail(user_chat_id: str = "chat-123") -> ChannelTalkUserChatDetail:
    return ChannelTalkUserChatDetail.from_api_payload(
        {
            "id": user_chat_id,
            "channelId": "channel-123",
            "state": ChannelTalkUserChatState.OPENED.value,
            "name": "Payment issue",
            "createdAt": "2026-05-22T01:00:00Z",
        },
        user_chat_id=user_chat_id,
    )


def _message(message_id: str, user_chat_id: str = "chat-123") -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": message_id,
            "chatId": user_chat_id,
            "personType": "manager",
            "plainText": f"message:{message_id}",
            "createdAt": "2026-05-22T01:01:00Z",
        },
        user_chat_id=user_chat_id,
    )


@pytest.mark.asyncio
async def test_first_page_fetches_detail_and_messages_concurrently() -> None:
    detail_started = asyncio.Event()
    messages_started = asyncio.Event()

    async def get_user_chat(**_kwargs):
        detail_started.set()
        await messages_started.wait()
        return _detail()

    async def list_user_chat_messages_page(**_kwargs):
        messages_started.set()
        await detail_started.wait()
        return ChannelTalkUserChatMessagePage(
            messages=[_message("msg-1")],
            next_cursor="cursor-2",
        )

    client = SimpleNamespace(
        get_user_chat=AsyncMock(side_effect=get_user_chat),
        list_user_chat_messages_page=AsyncMock(side_effect=list_user_chat_messages_page),
    )
    fetcher = ChannelTalkUserChatOriginalFetcher(client=client)

    page = await asyncio.wait_for(
        fetcher.fetch_user_chat_original_page(
            connection=_connection(),
            user_chat_id="chat-123",
        ),
        timeout=1,
    )

    assert page.detail is not None
    assert page.detail.user_chat_id == "chat-123"
    assert [message.message_id for message in page.messages] == ["msg-1"]
    assert page.next_cursor == "cursor-2"
    client.get_user_chat.assert_awaited_once_with(
        access_key="access-key",
        access_secret="access-secret",
        channel_id="channel-123",
        user_chat_id="chat-123",
    )
    client.list_user_chat_messages_page.assert_awaited_once_with(
        access_key="access-key",
        access_secret="access-secret",
        channel_id="channel-123",
        user_chat_id="chat-123",
        cursor=None,
        limit=500,
        sort_order="asc",
    )


@pytest.mark.asyncio
async def test_follow_up_page_fetches_messages_only_with_cursor() -> None:
    client = SimpleNamespace(
        get_user_chat=AsyncMock(),
        list_user_chat_messages_page=AsyncMock(
            return_value=ChannelTalkUserChatMessagePage(
                messages=[_message("msg-2")],
                next_cursor=None,
            )
        ),
    )
    fetcher = ChannelTalkUserChatOriginalFetcher(client=client)

    page = await fetcher.fetch_user_chat_original_page(
        connection=_connection(),
        user_chat_id="chat-123",
        cursor="cursor-2",
        limit=100,
    )

    assert page.detail is None
    assert [message.message_id for message in page.messages] == ["msg-2"]
    assert page.next_cursor is None
    client.get_user_chat.assert_not_awaited()
    client.list_user_chat_messages_page.assert_awaited_once_with(
        access_key="access-key",
        access_secret="access-secret",
        channel_id="channel-123",
        user_chat_id="chat-123",
        cursor="cursor-2",
        limit=100,
        sort_order="asc",
    )


@pytest.mark.asyncio
async def test_fetcher_rejects_non_positive_limit() -> None:
    fetcher = ChannelTalkUserChatOriginalFetcher(client=SimpleNamespace())

    with pytest.raises(ValueError, match="limit must be positive"):
        await fetcher.fetch_user_chat_original_page(
            connection=_connection(),
            user_chat_id="chat-123",
            limit=0,
        )


@pytest.mark.asyncio
async def test_client_page_wrapper_passes_cursor_as_since() -> None:
    client = ChannelTalkCoreApiClient()
    expected_page = ChannelTalkUserChatMessagePage(messages=[], next_cursor=None)
    client.list_user_chat_messages = AsyncMock(return_value=expected_page)

    page = await client.list_user_chat_messages_page(
        access_key="access-key",
        access_secret="access-secret",
        channel_id="channel-123",
        user_chat_id="chat-123",
        cursor="cursor-2",
        limit=100,
        sort_order="asc",
    )

    assert page is expected_page
    client.list_user_chat_messages.assert_awaited_once_with(
        access_key="access-key",
        access_secret="access-secret",
        channel_id="channel-123",
        user_chat_id="chat-123",
        since="cursor-2",
        limit=100,
        sort_order="asc",
    )
