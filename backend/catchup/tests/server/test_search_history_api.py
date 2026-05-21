from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import ManualSearchHistory
from catchup.db.models import User
from catchup.server.main import app
from catchup.server.search.dependencies import get_manual_search_service
from catchup.server.search.dependencies import get_search_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_db():
    db = MagicMock()
    db.scalar.return_value = 0
    db.scalars.return_value.all.return_value = []
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
def mock_search_service():
    service = MagicMock()
    service.search = AsyncMock(return_value=[])
    app.dependency_overrides[get_manual_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_manual_search_service, None)


@pytest.fixture
def mock_pgvector_service():
    service = MagicMock()
    service.hybrid_search = AsyncMock(return_value=[])
    app.dependency_overrides[get_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_search_service, None)


# ─── hybrid_search: history recording & audit ────────────────────────────────

def test_hybrid_search_saves_query_to_history(
    mock_db, mock_current_user, mock_search_service, mock_pgvector_service
):
    with patch("catchup.server.search.api.save_search_query") as mock_save:
        client.get("/api/v1/search/hybrid", params={"keyword": "PR 리뷰"})

    mock_save.assert_called_once_with(mock_db, 42, "PR 리뷰")
    mock_db.commit.assert_called_once()


def test_hybrid_search_emits_audit_event(
    mock_db, mock_current_user, mock_search_service, mock_pgvector_service
):
    with patch("catchup.server.search.api.save_search_query"):
        with patch("catchup.audit.emitters.bus") as mock_bus:
            client.get("/api/v1/search/hybrid", params={"keyword": "감사 테스트"})

    mock_bus.emit.assert_called_once()
    call_kwargs = mock_bus.emit.call_args.kwargs
    assert call_kwargs["action"].value == "search"
    assert call_kwargs["status"].value == "success"
    assert call_kwargs["metadata"].query == "감사 테스트"
    assert call_kwargs["metadata"].user_id == 42


def test_hybrid_search_does_not_save_on_unauthenticated(
    mock_db, mock_search_service, mock_pgvector_service
):
    app.dependency_overrides.pop(get_current_user, None)
    with patch("catchup.server.search.api.save_search_query") as mock_save:
        response = client.get("/api/v1/search/hybrid", params={"keyword": "test"})

    assert response.status_code == 401
    mock_save.assert_not_called()


# ─── GET /api/v1/search/queries ──────────────────────────────────────────────

def test_get_search_history_returns_200(mock_current_user, mock_db):
    response = client.get("/api/v1/search/queries")

    assert response.status_code == 200


def test_get_search_history_returns_pagination_shape(mock_current_user, mock_db):
    response = client.get("/api/v1/search/queries")
    data = response.json()

    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "items" in data


def test_get_search_history_default_page_and_size(mock_current_user, mock_db):
    response = client.get("/api/v1/search/queries")
    data = response.json()

    assert data["page"] == 1
    assert data["size"] == 20


def test_get_search_history_returns_items(mock_current_user, mock_db):
    record = MagicMock(spec=ManualSearchHistory)
    record.id = 1
    record.query = "슬랙 검색"
    record.created_at = datetime(2026, 5, 13, 10, 0, 0)
    mock_db.scalar.return_value = 1
    mock_db.scalars.return_value.all.return_value = [record]

    response = client.get("/api/v1/search/queries")
    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["query"] == "슬랙 검색"
    assert data["items"][0]["id"] == 1


def test_get_search_history_unauthenticated_returns_401(mock_db):
    app.dependency_overrides.pop(get_current_user, None)
    response = client.get("/api/v1/search/queries")

    assert response.status_code == 401


def test_get_search_history_period_param_accepted(mock_current_user, mock_db):
    for period in ["today", "7d", "all"]:
        response = client.get("/api/v1/search/queries", params={"period": period})
        assert response.status_code == 200, f"period={period} should return 200"


def test_get_search_history_custom_page_size(mock_current_user, mock_db):
    response = client.get(
        "/api/v1/search/queries", params={"page": 2, "size": 10}
    )
    data = response.json()

    assert data["page"] == 2
    assert data["size"] == 10
