"""ManualSearchService 단위 테스트."""
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from catchup.rag.schemas.structures import VectorDbSearchQuery


def _make_planned_search(
    query: str = "semantic query in English",
    keyword_tokens: list[str] | None = None,
) -> VectorDbSearchQuery:
    return VectorDbSearchQuery(
        query=query,
        keyword_tokens=keyword_tokens or [],
        reasoning="test",
    )


def _make_planner_state(planned: VectorDbSearchQuery, keyword: str = "q") -> dict:
    return {
        "original_query": keyword,
        "last_planned_query": keyword,
        "planned_search": planned,
    }


@pytest.fixture
def mock_planner():
    planner = MagicMock()
    planner.ainvoke = AsyncMock()
    return planner


@pytest.fixture
def mock_vector_db():
    service = MagicMock()
    service.hybrid_search = AsyncMock(return_value=[])
    return service


@pytest.fixture
def service(mock_planner):
    from catchup.search.service import ManualSearchService

    svc = ManualSearchService()
    svc._app = mock_planner
    return svc


@pytest.mark.asyncio
async def test_search_uses_planned_query(service, mock_planner, mock_vector_db):
    """hybrid_search에 planned_search.query와 keyword_tokens가 전달된다."""
    planned = _make_planned_search(
        query="English optimized query", keyword_tokens=["MyClass"]
    )
    mock_planner.ainvoke.return_value = _make_planner_state(planned, "Korean query")

    await service.search(
        user_id=1,
        keyword="Korean query",
        limit=10,
        offset=0,
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    assert kwargs["query"] == "English optimized query"
    assert kwargs["keyword_tokens"] == ["MyClass"]
    assert kwargs["k"] == 10
    assert kwargs["offset"] == 0


@pytest.mark.asyncio
async def test_search_thread_id_uses_user_id(service, mock_planner, mock_vector_db):
    """thread_id = 'search:{user_id}'로 플래너를 호출한다."""
    mock_planner.ainvoke.return_value = _make_planner_state(_make_planned_search())

    await service.search(
        user_id=99,
        keyword="q",
        limit=20,
        offset=0,
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    config = mock_planner.ainvoke.call_args[1]["config"]
    assert config["configurable"]["thread_id"] == "search:99"


@pytest.mark.asyncio
async def test_search_returns_base_sources(service, mock_planner, mock_vector_db):
    """docs를 BaseSource 리스트로 변환해 반환한다."""
    from langchain_core.documents import Document

    mock_planner.ainvoke.return_value = _make_planner_state(_make_planned_search())
    mock_vector_db.hybrid_search.return_value = [
        Document(
            page_content="content",
            metadata={
                "source": "slack",
                "entity_type": "message",
                "summary": "Title",
                "score": 0.75,
            },
            id="doc1",
        )
    ]

    results = await service.search(
        user_id=1,
        keyword="q",
        limit=20,
        offset=0,
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    assert len(results) == 1
    assert results[0].title == "Title"
    assert results[0].index == 1
