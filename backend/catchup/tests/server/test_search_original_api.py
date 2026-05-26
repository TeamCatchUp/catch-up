from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.search.original.ids import OriginalDocumentIdError
from catchup.search.original.resolvers.channel_talk import ChannelTalkOriginalError
from catchup.search.original.resolvers.slack import SlackOriginalError
from catchup.search.original.schemas.channel_talk import ChannelTalkOriginalAuthor
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalContent,
)
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalContentResponse,
)
from catchup.search.original.schemas.channel_talk import ChannelTalkUserChatOriginalItem
from catchup.search.original.schemas.slack import SlackMessageOriginalContentResponse
from catchup.search.original.schemas.slack import SlackMessageOriginalRawItem
from catchup.server.main import app
from catchup.server.search.dependencies import get_original_search_service
from catchup.server.search.schemas import OriginalFileUrlResponse

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_db():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def mock_current_user():
    user = MagicMock(spec=User)
    user.id = 42
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_original_search_service():
    service = MagicMock()
    service.get_original = AsyncMock(
        return_value=ChannelTalkUserChatOriginalContentResponse(
            connector=SourceType.CHANNEL_TALK,
            entity_type="user_chat",
            document_id="channel_talk:user_chat:channel-123:chat-456",
            title="결제 오류 문의",
            url="https://desk.channel.io/#/channels/channel-123/user_chats/chat-456",
            items=[
                ChannelTalkUserChatOriginalItem(
                    id="msg-1",
                    type="message",
                    visibility="public",
                    author=ChannelTalkOriginalAuthor(
                        id="user-123",
                        name="Customer Kim",
                        type="customer",
                    ),
                    contents=[
                        ChannelTalkUserChatOriginalContent(
                            content_type="text",
                            payload={"text": "결제가 안 됩니다."},
                        )
                    ],
                    created_at=datetime(2026, 5, 22, 1, 0, tzinfo=timezone.utc),
                )
            ],
            metadata={"channel_id": "channel-123"},
            next_cursor=None,
            fetched_at=datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
        )
    )
    app.dependency_overrides[get_original_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_original_search_service, None)


def test_original_search_endpoint_delegates_to_service(
    mock_current_user,
    mock_original_search_service,
):
    response = client.post(
        "/api/v1/search/original",
        json={
            "connector": "channel_talk",
            "document_id": "channel_talk:user_chat:channel-123:chat-456",
            "next_cursor": None,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["connector"] == "channel_talk"
    assert data["entity_type"] == "user_chat"
    assert data["document_id"] == "channel_talk:user_chat:channel-123:chat-456"
    assert data["items"] == [
        {
            "id": "msg-1",
            "type": "message",
            "visibility": "public",
            "author": {
                "id": "user-123",
                "name": "Customer Kim",
                "type": "customer",
                "email": None,
                "avatar_url": None,
            },
            "contents": [
                {
                    "content_type": "text",
                    "payload": {
                        "text": "결제가 안 됩니다.",
                    },
                }
            ],
            "created_at": "2026-05-22T01:00:00Z",
            "updated_at": None,
        }
    ]
    assert "body" not in data["items"][0]
    assert "metadata" not in data["items"][0]
    assert data["metadata"] == {"channel_id": "channel-123"}
    assert data["next_cursor"] is None
    mock_original_search_service.get_original.assert_awaited_once()
    _, kwargs = mock_original_search_service.get_original.call_args
    assert kwargs["request"].connector == SourceType.CHANNEL_TALK
    assert kwargs["request"].next_cursor is None
    assert "db" not in kwargs


def test_original_search_endpoint_passes_next_cursor(
    mock_current_user,
    mock_original_search_service,
):
    client.post(
        "/api/v1/search/original",
        json={
            "connector": "channel_talk",
            "document_id": "channel_talk:user_chat:channel-123:chat-456",
            "next_cursor": "cursor-2",
        },
    )

    _, kwargs = mock_original_search_service.get_original.call_args
    assert kwargs["request"].next_cursor == "cursor-2"


def test_original_search_endpoint_serializes_slack_raw_payload(
    mock_current_user,
    mock_original_search_service,
):
    raw_payload = {
        "ok": True,
        "messages": [
            {
                "type": "message",
                "user": "U1",
                "text": "테스트",
                "ts": "1716400000.000100",
                "blocks": [{"type": "rich_text"}],
            }
        ],
        "has_more": False,
    }
    mock_original_search_service.get_original = AsyncMock(
        return_value=SlackMessageOriginalContentResponse(
            connector=SourceType.SLACK,
            entity_type="message",
            document_id="slack:message:T1:C1:1716400000.000100",
            title="테스트",
            url="https://catchup--hq.slack.com/archives/C1/p1716400000000100",
            items=[
                SlackMessageOriginalRawItem(
                    id="1716400000.000100",
                    raw_payload=raw_payload,
                )
            ],
            metadata={
                "team_id": "T1",
                "channel_id": "C1",
                "thread_ts": "1716400000.000100",
                "users_by_id": {},
            },
            next_cursor=None,
            fetched_at=datetime(2026, 5, 24, 1, 0, tzinfo=timezone.utc),
        )
    )

    response = client.post(
        "/api/v1/search/original",
        json={
            "connector": "slack",
            "document_id": "slack:message:T1:C1:1716400000.000100",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["connector"] == "slack"
    assert data["entity_type"] == "message"
    assert data["title"] == "테스트"
    assert data["items"] == [
        {
            "id": "1716400000.000100",
            "type": "slack_conversations_replies_raw",
            "raw_payload": raw_payload,
            "created_at": None,
            "updated_at": None,
        }
    ]
    assert "contents" not in data["items"][0]
    assert "cache_misses" not in data["metadata"]


def test_original_file_url_endpoint_delegates_to_service(
    mock_current_user,
    mock_original_search_service,
):
    mock_original_search_service.get_original_file_url = AsyncMock(
        return_value=OriginalFileUrlResponse(
            connector=SourceType.CHANNEL_TALK,
            entity_type="user_chat",
            document_id="channel_talk:user_chat:channel-123:chat-456",
            file_key="file-1",
            url="https://signed.example/file",
            expires_in_seconds=900,
            fetched_at=datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
        )
    )

    response = client.post(
        "/api/v1/search/original/file-url",
        json={
            "connector": "channel_talk",
            "document_id": "channel_talk:user_chat:channel-123:chat-456",
            "file_key": "file-1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "connector": "channel_talk",
        "entity_type": "user_chat",
        "document_id": "channel_talk:user_chat:channel-123:chat-456",
        "file_key": "file-1",
        "url": "https://signed.example/file",
        "expires_in_seconds": 900,
        "fetched_at": "2026-05-22T02:00:00Z",
    }
    mock_original_search_service.get_original_file_url.assert_awaited_once()
    _, kwargs = mock_original_search_service.get_original_file_url.call_args
    assert kwargs["request"].connector == SourceType.CHANNEL_TALK
    assert kwargs["request"].file_key == "file-1"
    assert "db" not in kwargs


def test_original_file_url_endpoint_preserves_resolver_error_status(
    mock_current_user,
    mock_original_search_service,
):
    mock_original_search_service.get_original_file_url = AsyncMock(
        side_effect=ChannelTalkOriginalError(
            "Channel Talk API rate limit exceeded",
            status_code=429,
        )
    )

    response = client.post(
        "/api/v1/search/original/file-url",
        json={
            "connector": "channel_talk",
            "document_id": "channel_talk:user_chat:channel-123:chat-456",
            "file_key": "file-1",
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Channel Talk API rate limit exceeded"


def test_original_search_endpoint_preserves_slack_resolver_error_status(
    mock_current_user,
    mock_original_search_service,
):
    mock_original_search_service.get_original.side_effect = SlackOriginalError(
        "slack missing scope",
        status_code=403,
    )

    response = client.post(
        "/api/v1/search/original",
        json={
            "connector": "slack",
            "document_id": "slack:message:T1:C1:1716400000.000100",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "slack missing scope"


def test_original_search_endpoint_maps_bad_document_id_to_400(
    mock_current_user,
    mock_original_search_service,
):
    mock_original_search_service.get_original.side_effect = OriginalDocumentIdError(
        "bad document id"
    )

    response = client.post(
        "/api/v1/search/original",
        json={
            "connector": "channel_talk",
            "document_id": "channel_talk:user_chat:channel-123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad document id"


def test_original_search_endpoint_requires_auth(mock_original_search_service):
    app.dependency_overrides.pop(get_current_user, None)

    response = client.post(
        "/api/v1/search/original",
        json={
            "connector": "channel_talk",
            "document_id": "channel_talk:user_chat:channel-123:chat-456",
        },
    )

    assert response.status_code == 401
