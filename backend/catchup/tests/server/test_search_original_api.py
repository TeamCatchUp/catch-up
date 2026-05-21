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
from catchup.search.original.schemas import OriginalSearchResponse
from catchup.server.main import app
from catchup.server.search.dependencies import get_original_search_service

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
        return_value=OriginalSearchResponse(
            connector=SourceType.CHANNEL_TALK,
            entity_type="user_chat",
            document_id="channel_talk:user_chat:channel-123:chat-456",
            title="결제 오류 문의",
            url="https://desk.channel.io/#/channels/channel-123/user_chats/chat-456",
            items=[],
            metadata={"channel_id": "channel-123"},
            next_cursor=None,
            fetched_at=datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc),
        )
    )
    app.dependency_overrides[get_original_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_original_search_service, None)


def test_original_search_endpoint_delegates_to_service(
    mock_db,
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
    assert data["items"] == []
    assert data["metadata"] == {"channel_id": "channel-123"}
    assert data["next_cursor"] is None
    mock_original_search_service.get_original.assert_awaited_once()
    _, kwargs = mock_original_search_service.get_original.call_args
    assert kwargs["request"].connector == SourceType.CHANNEL_TALK
    assert kwargs["request"].next_cursor is None
    assert kwargs["db"] is mock_db


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
