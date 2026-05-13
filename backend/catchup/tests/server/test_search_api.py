from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.server.main import app
from catchup.server.search.dependencies import get_manual_search_service
from catchup.server.search.dependencies import get_search_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_db():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def mock_pgvector_service():
    service = MagicMock()
    service.hybrid_search = AsyncMock(return_value=[])
    app.dependency_overrides[get_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_search_service, None)


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


def test_hybrid_search_endpoint(
    mock_pgvector_service, mock_current_user, mock_search_service
):
    from langchain_core.documents import Document

    from catchup.rag.schemas.sources import BaseSource

    doc = Document(
        page_content="Hybrid Content",
        metadata={
            "source": "slack",
            "entity_type": "message",
            "summary": "Title",
            "score": 0.8,
        },
        id="id1",
    )
    mock_search_service.search.return_value = (
        [BaseSource.from_document(index=1, doc=doc, relevance_score=0.8)],
        1,
    )

    response = client.get(
        "/api/v1/search/hybrid",
        params={"keyword": "query", "limit": 5, "offset": 10, "tool_filters": ["slack"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Title"
    assert data["total"] == 1

    mock_search_service.search.assert_called_once_with(
        user=mock_current_user,
        keyword="query",
        limit=5,
        offset=10,
        tool_filters=["slack"],
        vector_db_service=mock_pgvector_service,
    )


def test_search_delegates_to_service(
    mock_pgvector_service, mock_current_user, mock_search_service
):
    """API는 search_service.search()에 올바른 파라미터를 전달한다."""
    mock_search_service.search.return_value = ([], 0)

    client.get(
        "/api/v1/search/hybrid",
        params={"keyword": "테스트 쿼리", "limit": 10, "offset": 20},
    )

    mock_search_service.search.assert_called_once_with(
        user=mock_current_user,
        keyword="테스트 쿼리",
        limit=10,
        offset=20,
        tool_filters=None,
        vector_db_service=mock_pgvector_service,
    )


def test_unauthenticated_request_returns_401(mock_pgvector_service, mock_search_service):
    """auth override 없이 요청하면 401을 반환한다."""
    app.dependency_overrides.pop(get_current_user, None)
    response = client.get("/api/v1/search/hybrid", params={"keyword": "test"})
    assert response.status_code == 401
