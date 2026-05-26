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
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
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
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalFileUrlRequest


class _FakeRepository:
    def __init__(self, credentials):
        self.credentials = credentials
        self.calls = []

    def get_connection(self, *, channel_id=None):
        self.calls.append(channel_id)
        return self.credentials


class _FakeMetadataRepository:
    def __init__(self, managers=None):
        self.managers = managers or []
        self.calls = []

    def list_managers_by_channel_and_ids(self, channel_id, manager_ids):
        self.calls.append((channel_id, manager_ids))
        return [
            manager
            for manager in self.managers
            if manager.manager_id in manager_ids
        ]


class _FakeFetcher:
    def __init__(self, page):
        self.page = page
        self.calls = []

    async def fetch_user_chat_original_page(self, **kwargs):
        self.calls.append(kwargs)
        return self.page


class _FakeClient:
    def __init__(self, file_url="https://signed.example/file"):
        self.file_url = file_url
        self.calls = []

    async def get_user_chat_file_url(self, **kwargs):
        self.calls.append(kwargs)
        return self.file_url


class _TrackingSession:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("db_open")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("db_close")
        return False


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
                "mobileNumber": "010-1234-5678",
                "landlineNumber": "02-1234-5678",
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


def _text_file_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-1",
            "chatId": "chat-456",
            "type": "chat",
            "personType": "user",
            "personId": "user-123",
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


def _block_button_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-2",
            "chatId": "chat-456",
            "type": "chat",
            "personType": "manager",
            "personId": "manager-1",
            "manager": {
                "id": "manager-1",
                "name": "Agent Lee",
                "email": "lee@example.com",
            },
            "blocks": [
                {
                    "type": "text",
                    "value": (
                        "<b>굵게</b> <i>기울임</i> "
                        '<link type="url" value="https://github.com/forrestchan">'
                        "리포지토리</link>"
                    ),
                }
            ],
            "buttons": [
                {
                    "title": "리포지토리",
                    "action": "web",
                    "url": "https://github.com/forrestchan",
                }
            ],
            "createdAt": "2026-05-22T01:02:00Z",
        },
        user_chat_id="chat-456",
    )


def _form_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-3",
            "chatId": "chat-456",
            "type": "form",
            "personType": "manager",
            "personId": "manager-1",
            "options": ["private"],
            "form": {
                "type": "custom",
                "submittedAt": "2026-05-22T01:03:00Z",
                "inputs": [
                    {
                        "type": "singleSelect",
                        "dataType": "string",
                        "label": "저희 서비스를 알게 된 경로",
                        "value": "검색",
                        "readOnly": True,
                    }
                ],
            },
            "createdAt": "2026-05-22T01:03:00Z",
        },
        user_chat_id="chat-456",
    )


def _bot_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-4",
            "chatId": "chat-456",
            "type": "chat",
            "personType": "bot",
            "personId": "bot-1",
            "botName": "Catch Up",
            "plainText": "방문해주셔서 감사합니다.",
            "createdAt": "2026-05-22T01:03:30Z",
        },
        user_chat_id="chat-456",
    )


def _customer_profile_form_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-5",
            "chatId": "chat-456",
            "type": "form",
            "personType": "manager",
            "personId": "manager-1",
            "form": {
                "type": "custom",
                "inputs": [
                    {
                        "label": "이름",
                        "bindingKey": "user.profile.name",
                        "type": "text",
                        "dataType": "string",
                        "value": "유저이름",
                    },
                    {
                        "label": "이메일",
                        "bindingKey": "user.profile.email",
                        "type": "text",
                        "dataType": "string",
                        "value": "customer@example.com",
                    },
                    {
                        "label": "휴대폰 번호",
                        "bindingKey": "user.profile.mobileNumber",
                        "type": "text",
                        "dataType": "string",
                        "value": "010-9876-5432",
                    },
                    {
                        "label": "유선 번호",
                        "bindingKey": "user.profile.landlineNumber",
                        "type": "text",
                        "dataType": "string",
                        "value": "031-3333-4444",
                    },
                ],
            },
            "createdAt": "2026-05-22T01:04:00Z",
        },
        user_chat_id="chat-456",
    )


def _manager_without_profile_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-6",
            "chatId": "chat-456",
            "type": "chat",
            "personType": "manager",
            "personId": "manager-1",
            "plainText": "프로필 없음",
            "createdAt": "2026-05-22T01:05:00Z",
        },
        user_chat_id="chat-456",
    )


def _manager_metadata() -> ChannelTalkManagerMetadata:
    return ChannelTalkManagerMetadata(
        channel_id="channel-123",
        manager_id="manager-1",
        name="Agent Lee",
        email="lee@example.com",
        avatar_url="https://example.com/manager-avatar.png",
    )


def _log_message() -> ChannelTalkUserChatMessage:
    return ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-log",
            "chatId": "chat-456",
            "personType": "manager",
            "personId": "manager-1",
            "log": {"action": "close"},
            "createdAt": "2026-05-22T01:04:00Z",
        },
        user_chat_id="chat-456",
    )


@pytest.mark.asyncio
async def test_channel_talk_resolver_maps_first_page_detail_and_messages() -> None:
    repository = _FakeRepository(_credentials())
    fetcher = _FakeFetcher(
        ChannelTalkUserChatOriginalPage(
            detail=_detail(),
            messages=(
                _text_file_message(),
                _block_button_message(),
                _form_message(),
                _bot_message(),
                _log_message(),
            ),
            next_cursor="cursor-2",
        )
    )
    resolver = ChannelTalkOriginalResolver(
        fetcher=fetcher,
        repository_factory=lambda _db: repository,
        metadata_repository_factory=lambda _db: _FakeMetadataRepository(),
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
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
    assert (
        response.url
        == "https://desk.channel.io/#/channels/channel-123/user_chats/chat-456"
    )
    assert response.next_cursor == "cursor-2"
    assert response.fetched_at.isoformat() == "2026-05-22T02:00:00+00:00"
    assert response.metadata["channel_id"] == "channel-123"
    assert response.metadata["channel_name"] == "Support"
    assert response.metadata["state"] == "opened"
    assert response.metadata["priority"] == "urgent"
    assert response.metadata["name"] == "Payment issue"
    assert response.metadata["description"] == "결제 오류 문의"
    assert response.metadata["customer"]["name"] == "Customer Kim"
    assert response.metadata["customer"]["email"] == "kim@example.com"
    assert response.metadata["customer"]["mobile_number"] == "010-1234-5678"
    assert response.metadata["customer"]["landline_number"] == "02-1234-5678"
    assert response.metadata["assignment"]["assignee_name"] == "Agent Lee"
    assert response.metadata["tags"] == [{"key": "payment", "name": "Payment"}]
    assert [item.id for item in response.items] == [
        "msg-1",
        "msg-2",
        "msg-3",
        "msg-4",
    ]

    text_file_item = response.items[0]
    assert text_file_item.type == "message"
    assert text_file_item.visibility == "public"
    assert text_file_item.author is not None
    assert text_file_item.author.type == "customer"
    assert text_file_item.author.name == "Customer Kim"
    assert text_file_item.author.email == "kim@example.com"
    assert text_file_item.author.avatar_url == "https://example.com/avatar.png"
    assert [content.content_type for content in text_file_item.contents] == [
        "text",
        "file",
    ]
    assert text_file_item.contents[0].payload == {"text": "결제가 안 됩니다."}
    assert text_file_item.contents[1].payload == {
        "files": [
            {
                "file_key": "file-1",
                "name": "receipt.png",
                "content_type": "image/png",
            }
        ]
    }

    block_button_item = response.items[1]
    assert block_button_item.visibility == "public"
    assert [content.content_type for content in block_button_item.contents] == [
        "block",
        "button",
    ]
    assert block_button_item.contents[0].payload == {
        "blocks": [
            {
                "block_type": "text",
                "text": (
                    "<b>굵게</b> <i>기울임</i> "
                    '<link type="url" value="https://github.com/forrestchan">'
                    "리포지토리</link>"
                ),
                "value": (
                    "<b>굵게</b> <i>기울임</i> "
                    '<link type="url" value="https://github.com/forrestchan">'
                    "리포지토리</link>"
                ),
                "markdown": "**굵게** *기울임* [리포지토리](https://github.com/forrestchan)",
                "raw_payload": {
                    "type": "text",
                    "value": (
                        "<b>굵게</b> <i>기울임</i> "
                        '<link type="url" value="https://github.com/forrestchan">'
                        "리포지토리</link>"
                    ),
                },
            }
        ]
    }
    assert block_button_item.contents[1].payload == {
        "buttons": [
            {
                "text": "리포지토리",
                "action": "web",
                "url": "https://github.com/forrestchan",
            }
        ]
    }

    form_item = response.items[2]
    assert form_item.visibility == "internal"
    assert [content.content_type for content in form_item.contents] == ["form"]
    assert form_item.contents[0].payload == {
        "form": {
            "form_type": "custom",
            "submitted_at": "2026-05-22T01:03:00Z",
            "inputs": [
                {
                    "label": "저희 서비스를 알게 된 경로",
                    "input_type": "singleSelect",
                    "data_type": "string",
                    "value": "검색",
                }
            ],
            "raw_payload": {
                "type": "custom",
                "submittedAt": "2026-05-22T01:03:00Z",
                "inputs": [
                    {
                        "type": "singleSelect",
                        "dataType": "string",
                        "label": "저희 서비스를 알게 된 경로",
                        "value": "검색",
                        "readOnly": True,
                    }
                ],
            },
        }
    }

    bot_item = response.items[3]
    assert bot_item.author is not None
    assert bot_item.author.type == "manager"
    assert bot_item.author.name == "Catch Up"

    serialized_items = [
        item.model_dump(mode="json", exclude_none=True) for item in response.items
    ]
    assert all("body" not in item for item in serialized_items)
    assert all("metadata" not in item for item in serialized_items)
    assert all(item["type"] == "message" for item in serialized_items)
    assert all(
        content["content_type"] in {"text", "block", "button", "form", "file"}
        for item in serialized_items
        for content in item["contents"]
    )
    assert "attachments" not in response.metadata
    assert "buttons" not in response.metadata
    assert "blocks" not in response.metadata
    assert "forms" not in response.metadata
    assert "logs" not in response.metadata


@pytest.mark.asyncio
async def test_channel_talk_resolver_merges_customer_profile_from_form_inputs() -> None:
    detail = ChannelTalkUserChatDetail.from_api_payload(
        {
            "id": "chat-456",
            "channelId": "channel-123",
            "state": ChannelTalkUserChatState.OPENED.value,
            "priority": "urgent",
            "name": "Payment issue",
            "user": {
                "id": "user-123",
                "memberId": "member-123",
            },
        },
        user_chat_id="chat-456",
    )
    repository = _FakeRepository(_credentials())
    fetcher = _FakeFetcher(
        ChannelTalkUserChatOriginalPage(
            detail=detail,
            messages=(_customer_profile_form_message(),),
            next_cursor=None,
        )
    )
    resolver = ChannelTalkOriginalResolver(
        fetcher=fetcher,
        repository_factory=lambda _db: repository,
        metadata_repository_factory=lambda _db: _FakeMetadataRepository(),
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve(request=request, ref=ref, db=object())

    assert response.metadata["customer"]["name"] == "유저이름"
    assert response.metadata["customer"]["email"] == "customer@example.com"
    assert response.metadata["customer"]["mobile_number"] == "010-9876-5432"
    assert response.metadata["customer"]["landline_number"] == "031-3333-4444"


@pytest.mark.asyncio
async def test_channel_talk_resolver_maps_manager_profile_from_manager_list() -> None:
    repository = _FakeRepository(_credentials())
    metadata_repository = _FakeMetadataRepository(managers=[_manager_metadata()])
    fetcher = _FakeFetcher(
        ChannelTalkUserChatOriginalPage(
            detail=_detail(),
            messages=(_manager_without_profile_message(),),
            next_cursor=None,
        )
    )
    resolver = ChannelTalkOriginalResolver(
        fetcher=fetcher,
        repository_factory=lambda _db: repository,
        metadata_repository_factory=lambda _db: metadata_repository,
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve(request=request, ref=ref, db=object())

    assert metadata_repository.calls == [("channel-123", {"manager-1"})]
    assert len(response.items) == 1
    item = response.items[0]
    assert item.author is not None
    assert item.author.type == "manager"
    assert item.author.id == "manager-1"
    assert item.author.name == "Agent Lee"
    assert item.author.email == "lee@example.com"
    assert item.author.avatar_url == "https://example.com/manager-avatar.png"


@pytest.mark.asyncio
async def test_channel_talk_resolver_skips_manager_lookup_without_manager_messages() -> None:
    repository = _FakeRepository(_credentials())
    metadata_repository = _FakeMetadataRepository(managers=[_manager_metadata()])
    fetcher = _FakeFetcher(
        ChannelTalkUserChatOriginalPage(
            detail=_detail(),
            messages=(_text_file_message(),),
            next_cursor=None,
        )
    )
    resolver = ChannelTalkOriginalResolver(
        fetcher=fetcher,
        repository_factory=lambda _db: repository,
        metadata_repository_factory=lambda _db: metadata_repository,
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve(request=request, ref=ref, db=object())

    assert metadata_repository.calls == []
    assert len(response.items) == 1
    assert response.items[0].author is not None
    assert response.items[0].author.type == "customer"


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
        metadata_repository_factory=lambda _db: _FakeMetadataRepository(),
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalContentRequest(
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
    request = OriginalContentRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    with pytest.raises(ChannelTalkOriginalError, match="credentials not found"):
        await resolver.resolve(request=request, ref=ref, db=object())


@pytest.mark.asyncio
async def test_channel_talk_resolver_fetches_single_file_url() -> None:
    repository = _FakeRepository(_credentials())
    client = _FakeClient(file_url="https://signed.example/receipt.png")
    resolver = ChannelTalkOriginalResolver(
        client=client,
        repository_factory=lambda _db: repository,
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalFileUrlRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
        file_key="file-1",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve_file_url(request=request, ref=ref, db=object())

    assert repository.calls == ["channel-123"]
    assert client.calls == [
        {
            "access_key": "access-key",
            "access_secret": "access-secret",
            "channel_id": "channel-123",
            "user_chat_id": "chat-456",
            "file_key": "file-1",
        }
    ]
    assert response.connector == SourceType.CHANNEL_TALK
    assert response.entity_type == "user_chat"
    assert response.document_id == "channel_talk:user_chat:channel-123:chat-456"
    assert response.file_key == "file-1"
    assert response.url == "https://signed.example/receipt.png"
    assert response.expires_in_seconds == 900
    assert response.fetched_at.isoformat() == "2026-05-22T02:00:00+00:00"


@pytest.mark.asyncio
async def test_channel_talk_resolver_closes_db_session_before_file_url_api_call() -> None:
    events = []

    class Repository:
        def get_connection(self, *, channel_id=None):
            events.append(f"db_query:{channel_id}")
            return _credentials()

    class Client:
        async def get_user_chat_file_url(self, **kwargs):
            events.append("api_call")
            return "https://signed.example/receipt.png"

    resolver = ChannelTalkOriginalResolver(
        client=Client(),
        repository_factory=lambda _db: Repository(),
        session_factory=lambda: _TrackingSession(events),
        clock=lambda: datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
    )
    request = OriginalFileUrlRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
        file_key="file-1",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    await resolver.resolve_file_url(request=request, ref=ref)

    assert events == [
        "db_open",
        "db_query:channel-123",
        "db_close",
        "api_call",
    ]
