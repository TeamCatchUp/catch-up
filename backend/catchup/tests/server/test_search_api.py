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


def test_hybrid_search_endpoint(mock_pgvector_service):
    from langchain_core.documents import Document

    # Mock response for hybrid_search
    mock_pgvector_service.hybrid_search.return_value = [
        Document(
            page_content="Hybrid Content",
            metadata={
                                "source": "slack",
                                "entity_type": "message",
                                "summary": "Title",
                                "score": 0.8
                            },
            id="id1"
        )
    ]

    response = client.get(
        "/api/v1/search/hybrid",
        params={"keyword": "query", "limit": 5, "offset": 10, "tool_filters": ["slack"], "score_threshold": 0.5}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Title"
    
    # Service 호출 검증
    mock_pgvector_service.hybrid_search.assert_called_once()
    args, kwargs = mock_pgvector_service.hybrid_search.call_args
    assert kwargs["query"] == "query"
    assert kwargs["k"] == 5
    assert kwargs["offset"] == 10
    assert kwargs["score_threshold"] == 0.5
    assert "slack" in [t.value for t in kwargs["tool_filters"]]
