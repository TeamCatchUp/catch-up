"""ManualSearchService 단위 테스트."""
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from catchup.db.models import User
from catchup.rag.schemas.structures import ManualSearchQuery
from catchup.search.planner.state import CachedSearch
from catchup.search.service import resolve


@pytest.mark.parametrize("intelligent_filter,explicit,inferred,expected", [
    # 명시값 항상 우선
    (True,  ["github"], ["slack"], ["github"]),
    (False, ["github"], ["slack"], ["github"]),
    # OFF + 명시 없음 → None (전체)
    (False, [],   ["slack"], None),
    (False, None, ["slack"], None),
    # ON + 명시 없음 + 추론 있음 → 추론 적용
    (True,  [],   ["slack"], ["slack"]),
    (True,  None, ["slack"], ["slack"]),
    # ON + 명시 없음 + 추론 없음 → None (fallback)
    (True,  [],   None, None),
    (True,  None, None, None),
])
def test_resolve(intelligent_filter, explicit, inferred, expected):
    assert resolve(intelligent_filter, explicit, inferred) == expected


def _make_planned_search(
    query: str = "semantic query in English",
    keyword_tokens: list[str] | None = None,
    inferred_tool_filters=None,
    start_date=None,
    end_date=None,
) -> ManualSearchQuery:
    return ManualSearchQuery(
        query=query,
        keyword_tokens=keyword_tokens or [],
        inferred_tool_filters=inferred_tool_filters,
        start_date=start_date,
        end_date=end_date,
        reasoning="test",
    )


def _make_planner_state(planned: ManualSearchQuery, keyword: str = "q") -> dict:
    return {
        "original_query": keyword,
        "query_cache": {keyword: CachedSearch(planned=planned)},
    }


def _make_user(user_id: int = 1) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = user_id
    user.name = "홍길동"
    user.department = "개발팀"
    return user


@pytest.fixture
def mock_user():
    return _make_user()


@pytest.fixture
def mock_planner():
    planner = MagicMock()
    planner.ainvoke = AsyncMock()
    return planner


@pytest.fixture
def mock_vector_db():
    service = MagicMock()
    service.hybrid_search = AsyncMock(return_value=[])
    service.session_factory = MagicMock()
    service.async_session_factory = MagicMock()
    service.collection_name = "test_collection"
    return service


def _assert_hybrid_search_called_with_pool(mock_vector_db, **expected_kwargs):
    """hybrid_search가 pool size(k=70)와 offset=0으로 호출됐는지 검증한다."""
    _, kwargs = mock_vector_db.hybrid_search.call_args
    assert kwargs.get("k") == 70
    assert kwargs.get("offset") == 0
    for key, value in expected_kwargs.items():
        assert kwargs[key] == value


@pytest.fixture
def service(mock_planner):
    from catchup.search.service import ManualSearchService

    svc = ManualSearchService()
    svc._app = mock_planner
    return svc


@pytest.mark.asyncio
async def test_search_uses_planned_query(service, mock_planner, mock_vector_db, mock_user):
    """hybrid_search에 planned_search.query와 keyword_tokens가 전달된다."""
    planned = _make_planned_search(
        query="English optimized query", keyword_tokens=["MyClass"]
    )
    mock_planner.ainvoke.return_value = _make_planner_state(planned, "Korean query")

    await service.search(
        user=mock_user,
        keyword="Korean query",
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    _assert_hybrid_search_called_with_pool(
        mock_vector_db,
        query="English optimized query",
        keyword_tokens=["MyClass"],
    )


@pytest.mark.asyncio
async def test_search_thread_id_uses_user_id(service, mock_planner, mock_vector_db):
    """thread_id = 'search:{user_id}'로 플래너를 호출한다."""
    mock_planner.ainvoke.return_value = _make_planner_state(_make_planned_search())

    await service.search(
        user=_make_user(user_id=99),
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    config = mock_planner.ainvoke.call_args[1]["config"]
    assert config["configurable"]["thread_id"] == "search:99"




@pytest.mark.asyncio
async def test_search_returns_base_sources(service, mock_planner, mock_vector_db, mock_user):
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

    results, total, source_distribution = await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    assert total == 1
    assert source_distribution == {"slack": 1}
    assert len(results) == 1
    assert results[0].title == "Title"
    assert results[0].index == 1


@pytest.mark.asyncio
async def test_search_passes_temporal_filters_to_hybrid_search(
    service, mock_planner, mock_vector_db, mock_user
):
    """start_date/end_date가 있으면 hybrid_search에 temporal_filters가 전달된다."""
    from datetime import datetime
    from datetime import timezone

    planned = _make_planned_search()
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
        start_date=start,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    temporal_filters = kwargs.get("temporal_filters")
    assert temporal_filters is not None
    assert len(temporal_filters) == 1
    assert temporal_filters[0].time_field == "created_at"
    assert temporal_filters[0].start_date == start
    assert temporal_filters[0].end_date > start


@pytest.mark.asyncio
async def test_search_no_temporal_filter_when_dates_absent(
    service, mock_planner, mock_vector_db, mock_user
):
    """start_date/end_date 둘 다 없으면 hybrid_search에 temporal_filters=None이 전달된다."""
    planned = _make_planned_search()
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    assert kwargs.get("temporal_filters") is None


@pytest.mark.asyncio
async def test_inferred_tool_filters_used_when_ui_absent(
    service, mock_planner, mock_vector_db, mock_user
):
    """UI tool_filters=None이면 planned.inferred_tool_filters가 hybrid_search에 전달된다."""
    from catchup.db.models import SourceType

    planned = _make_planned_search(
        inferred_tool_filters=[SourceType.SLACK]
    )
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    assert kwargs.get("tool_filters") == [SourceType.SLACK]


@pytest.mark.asyncio
async def test_ui_tool_filters_override_inferred(
    service, mock_planner, mock_vector_db, mock_user
):
    """UI tool_filters가 있으면 inferred_tool_filters를 덮어쓴다."""
    from catchup.db.models import SourceType

    planned = _make_planned_search(
        inferred_tool_filters=[SourceType.SLACK]
    )
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=[SourceType.GITHUB],
        vector_db_service=mock_vector_db,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    assert kwargs.get("tool_filters") == [SourceType.GITHUB]


@pytest.mark.asyncio
async def test_empty_ui_tool_filters_searches_all_sources(
    service, mock_planner, mock_vector_db, mock_user
):
    """UI tool_filters=[]이면 inferred를 무시하고 전체 소스 대상 검색한다."""
    from catchup.db.models import SourceType

    planned = _make_planned_search(inferred_tool_filters=[SourceType.SLACK])
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=[],
        vector_db_service=mock_vector_db,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    assert kwargs.get("tool_filters") == []


@pytest.mark.asyncio
async def test_inferred_dates_used_when_ui_absent(
    service, mock_planner, mock_vector_db, mock_user
):
    """UI 날짜 없으면 planned.start_date/end_date가 temporal_filters에 반영된다."""
    from datetime import datetime
    from datetime import timezone

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 7, tzinfo=timezone.utc)
    planned = _make_planned_search(start_date=start, end_date=end)
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    temporal_filters = kwargs.get("temporal_filters")
    assert temporal_filters is not None
    assert temporal_filters[0].start_date == start
    assert temporal_filters[0].end_date == end


@pytest.mark.asyncio
async def test_ui_dates_override_inferred_dates(
    service, mock_planner, mock_vector_db, mock_user
):
    """UI start_date/end_date가 있으면 planned 날짜를 덮어쓴다."""
    from datetime import datetime
    from datetime import timezone

    inferred_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ui_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    ui_end = datetime(2026, 3, 31, tzinfo=timezone.utc)

    planned = _make_planned_search(start_date=inferred_start)
    mock_planner.ainvoke.return_value = _make_planner_state(planned)

    await service.search(
        user=mock_user,
        keyword="q",
        tool_filters=None,
        vector_db_service=mock_vector_db,
        start_date=ui_start,
        end_date=ui_end,
    )

    _, kwargs = mock_vector_db.hybrid_search.call_args
    temporal_filters = kwargs.get("temporal_filters")
    assert temporal_filters is not None
    assert temporal_filters[0].start_date == ui_start
    assert temporal_filters[0].end_date == ui_end
