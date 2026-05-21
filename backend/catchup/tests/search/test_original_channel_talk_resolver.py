from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from catchup.connectors.channel_talk.core.user_chat_original_fetcher import (
    ChannelTalkUserChatOriginalPage,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.db.models import SourceType
from catchup.search.original.ids import parse_original_document_id
from catchup.search.original.resolvers.channel_talk import ChannelTalkOriginalError
from catchup.search.original.resolvers.channel_talk import ChannelTalkOriginalResolver
from catchup.search.original.schemas import OriginalSearchRequest


class _FakeRepository:
    def __init__(self, credentials):
        self.credentials = credentials
        self.calls = []

    def get_connection(self, *, channel_id=None):
        self.calls.append(channel_id)
        return self.credentials


class _FakeFetcher:
    def __init__(self, page):
        self.page = page
        self.calls = []

    async def fetch_user_chat_original_page(self, **kwargs):
        self.calls.append(kwargs)
        return self.page


def _credentials() -> ChannelTalkCredentialsRecord:
    return ChannelTalkCredentialsRecord(
        channel_id="channel-123",
        channel_name="Support",
        access_key="access-key",
        access_secret="access-secret",
        webhook_token="webhook-token",
    )


def _detail() -> ChannelTalkUserChatDetail:
    return ChannelTalkUserChatDetail.from_api_payload(
        {
            "id": "chat-456",
            "channelId": "channel-123",
            "state": ChannelTalkUserChatState.OPENED.value,
            "priority": "urgent",
            "name": "Payment issue",
            "description": "결제 오류 문의",
            "managed": True,
            "goalState": "resolved",
            "createdAt": "2026-05-22T01:00:00Z",
            "deskUpdatedAt": "2026-05-22T01:10:00Z",
            "user": {
                "id": "user-123",
                "memberId": "member-123",
                "name": "Customer Kim",
                "email": "kim@example.com",
                "avatarUrl": "https://example.com/avatar.png",
            },
            "assignee": {
                "id": "manager-1",
                "name": "Agent Lee",
                "email": "lee@example.com",
            },
            "tags": [{"key": "payment", "name": "Payment"}],
            "replyCount": 2,
        },
        user_chat_id="chat-456",
    )


def _message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-1",
            "chatId": "chat-456",
            "type": "chat",
            "personType": "user",
            "user": {
                "id": "user-123",
                "memberId": "member-123",
                "name": "Customer Kim",
                "email": "kim@example.com",
            },
            "plainText": "결제가 안 됩니다.",
            "createdAt": "2026-05-22T01:01:00Z",
            "files": [
                {
                    "key": "file-1",
                    "name": "receipt.png",
                    "contentType": "image/png",
                }
            ],
        },
        user_chat_id="chat-456",
    )


@pytest.mark.asyncio
async def test_channel_talk_resolver_maps_first_page_detail_and_messages() -> None:
    repository = _FakeRepository(_credentials())
    fetcher = _FakeFetcher(
        ChannelTalkUserChatOriginalPage(
            detail=_detail(),
            messages=(_message(),),
            next_cursor="cursor-2",
        )
    )
    resolver = ChannelTalkOriginalResolver(
        fetcher=fetcher,
        repository_factory=lambda _db: repository,
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalSearchRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve(request=request, ref=ref, db=object())

    assert repository.calls == ["channel-123"]
    assert fetcher.calls[0]["connection"].channel_id == "channel-123"
    assert fetcher.calls[0]["user_chat_id"] == "chat-456"
    assert fetcher.calls[0]["cursor"] is None
    assert response.connector == SourceType.CHANNEL_TALK
    assert response.entity_type == "user_chat"
    assert response.title == "결제 오류 문의"
    assert response.url == "https://desk.channel.io/#/channels/channel-123/user_chats/chat-456"
    assert response.next_cursor == "cursor-2"
    assert response.fetched_at.isoformat() == "2026-05-22T02:00:00+00:00"
    assert response.metadata["channel_id"] == "channel-123"
    assert response.metadata["channel_name"] == "Support"
    assert response.metadata["state"] == "opened"
    assert response.metadata["priority"] == "urgent"
    assert response.metadata["customer"]["email"] == "kim@example.com"
    assert response.metadata["assignment"]["assignee_name"] == "Agent Lee"
    assert response.metadata["tags"] == [{"key": "payment", "name": "Payment"}]
    assert len(response.items) == 1
    item = response.items[0]
    assert item.id == "msg-1"
    assert item.type == "message"
    assert item.author is not None
    assert item.author.type == "customer"
    assert item.author.name == "Customer Kim"
    assert item.body.text == "결제가 안 됩니다. | receipt.png (image/png)"
    assert item.metadata["visibility"] == "public"
    assert item.metadata["attachments"][0]["file_key"] == "file-1"


@pytest.mark.asyncio
async def test_channel_talk_resolver_follow_up_page_returns_minimal_metadata() -> None:
    repository = _FakeRepository(_credentials())
    fetcher = _FakeFetcher(
        ChannelTalkUserChatOriginalPage(
            detail=None,
            messages=(),
            next_cursor=None,
        )
    )
    resolver = ChannelTalkOriginalResolver(
        fetcher=fetcher,
        repository_factory=lambda _db: repository,
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalSearchRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
        next_cursor="cursor-2",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve(request=request, ref=ref, db=object())

    assert fetcher.calls[0]["cursor"] == "cursor-2"
    assert response.title == "chat-456"
    assert response.metadata == {
        "channel_id": "channel-123",
        "channel_name": "Support",
        "user_chat_id": "chat-456",
    }
    assert response.items == []
    assert response.next_cursor is None


@pytest.mark.asyncio
async def test_channel_talk_resolver_rejects_missing_credentials() -> None:
    repository = _FakeRepository(None)
    resolver = ChannelTalkOriginalResolver(
        fetcher=_FakeFetcher(ChannelTalkUserChatOriginalPage()),
        repository_factory=lambda _db: repository,
    )
    request = OriginalSearchRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    with pytest.raises(ChannelTalkOriginalError, match="credentials not found"):
        await resolver.resolve(request=request, ref=ref, db=object())
