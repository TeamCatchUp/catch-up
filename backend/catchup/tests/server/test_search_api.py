from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from catchup.server.main import app
from catchup.server.search.dependencies import get_search_service

client = TestClient(app)


@pytest.fixture
def mock_pgvector_service():
    service = MagicMock()
    app.dependency_overrides[get_search_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_keyword_search_endpoint(mock_pgvector_service):
    # Mock service response
    from langchain_core.documents import Document

    mock_pgvector_service.manual_keyword_search.return_value = [
        Document(
            page_content="Snippet...",
            metadata={
                "source": "slack",
                "entity_type": "message",
                "team_id": "T1",
                "channel_id": "C1",
                "ts": "123.456",
                "author_name": "User",
                "summary": "Summary",
                "contextual_content": "Snippet...",
            },
            id="slack:message:T1:C1:123.456",
        )
    ]

    response = client.get(
        "/api/v1/search/keyword", params={"keyword": "test", "limit": 10}
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["source"] == "slack"
    # snippet 대신 원본(또는 빈값)이 올 수 있음


def test_keyword_search_filters(mock_pgvector_service):
    mock_pgvector_service.manual_keyword_search.return_value = []

    response = client.get(
        "/api/v1/search/keyword",
        params={
            "keyword": "test",
            "tool_filters": ["slack", "jira"],
            "start_date": "2023-01-01T00:00:00Z",
            "end_date": "2023-12-31T23:59:59Z",
        },
    )

    assert response.status_code == 200
    # Service 호출 인자 검증 (통합 테스트이므로 실제 라우팅 확인)
    mock_pgvector_service.manual_keyword_search.assert_called_once()
    args, kwargs = mock_pgvector_service.manual_keyword_search.call_args
    assert kwargs["keyword"] == "test"
    # Query([])로 받으므로 리스트로 전달됨
    assert "slack" in [t.value for t in kwargs["integrations"]]
