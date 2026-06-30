"""plan_manual_search_node tests."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.schemas.structures import ManualSearchQuery
from catchup.search.planner.state import _QUERY_CACHE_MAX_SIZE
from catchup.search.planner.state import CachedSearch


def _make_state(
    original_query: str = "테스트 쿼리",
    query_cache: dict | None = None,
) -> dict:
    return {
        "original_query": original_query,
        "query_cache": query_cache or {},
    }


def _make_planned_search(
    query: str = "semantic query in English",
    keyword_tokens: list[str] | None = None,
) -> ManualSearchQuery:
    return ManualSearchQuery(
        query=query,
        keyword_tokens=keyword_tokens or [],
        reasoning="test reasoning",
    )


def _make_cached(planned: ManualSearchQuery) -> CachedSearch:
    return CachedSearch(planned=planned)


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_plan():
    """query_cache에 쿼리 존재 → LLM 미호출, query_cache만 반환."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    existing = _make_cached(_make_planned_search())
    state = _make_state(
        original_query="hello",
        query_cache={"hello": existing},
    )
    mock_llm = MagicMock()

    result = await plan_manual_search_node(state, llm=mock_llm)

    assert "planned_search" not in result
    assert result["query_cache"]["hello"].planned == existing.planned
    assert result["query_cache_hit"] is True
    mock_llm.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_moves_entry_to_recent():
    """캐시 히트 시 LRU 끝으로 이동, searched_at은 갱신되고 generated_at은 보존된다."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    cached_a = _make_cached(_make_planned_search(query="plan A"))
    original_generated_at = cached_a.generated_at
    original_searched_at = cached_a.searched_at
    cached_b = _make_cached(_make_planned_search(query="plan B"))
    state = _make_state(
        original_query="query_a",
        query_cache={"query_a": cached_a, "query_b": cached_b},
    )

    result = await plan_manual_search_node(state, llm=MagicMock())

    entry = result["query_cache"]["query_a"]
    assert list(result["query_cache"].keys()) == ["query_b", "query_a"]
    assert entry.generated_at == original_generated_at
    assert entry.searched_at >= original_searched_at


@pytest.mark.asyncio
async def test_cache_miss_calls_llm():
    """query_cache에 없으면 LLM 호출 후 CachedSearch로 캐시에 추가."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    planned = _make_planned_search(query="optimized English query")
    mock_llm = MagicMock()

    with (
        patch("catchup.search.planner.plan_manual_search.prompt_loader") as mock_loader,
        patch(
            "catchup.search.planner.plan_manual_search.ainvoke_llm_with_token_usage"
        ) as mock_invoke,
    ):
        mock_loader.get_prompt.return_value = [MagicMock()]
        mock_invoke.return_value = (
            {"parsed": planned, "raw": MagicMock()},
            {"token_breakdown": {}},
        )

        state = _make_state(original_query="new query")
        result = await plan_manual_search_node(state, llm=mock_llm)

    cached = result["query_cache"]["new query"]
    assert isinstance(cached, CachedSearch)
    assert cached.planned == planned
    assert result["query_cache_hit"] is False


@pytest.mark.asyncio
async def test_cache_evicts_lru_when_full():
    """캐시가 가득 찼을 때 가장 오래된 항목을 제거한다."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    oldest_key = "oldest_query"
    cache = {oldest_key: _make_cached(_make_planned_search(query="oldest"))}
    for i in range(1, _QUERY_CACHE_MAX_SIZE):
        cache[f"query_{i}"] = _make_cached(_make_planned_search(query=f"plan {i}"))

    assert len(cache) == _QUERY_CACHE_MAX_SIZE

    new_plan = _make_planned_search(query="new plan")
    mock_llm = MagicMock()

    with (
        patch("catchup.search.planner.plan_manual_search.prompt_loader") as mock_loader,
        patch(
            "catchup.search.planner.plan_manual_search.ainvoke_llm_with_token_usage"
        ) as mock_invoke,
    ):
        mock_loader.get_prompt.return_value = [MagicMock()]
        mock_invoke.return_value = (
            {"parsed": new_plan, "raw": MagicMock()},
            {"token_breakdown": {}},
        )

        state = _make_state(original_query="brand new query", query_cache=cache)
        result = await plan_manual_search_node(state, llm=mock_llm)

    assert oldest_key not in result["query_cache"]
    assert "brand new query" in result["query_cache"]
    assert len(result["query_cache"]) == _QUERY_CACHE_MAX_SIZE


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_raw_query():
    """LLM 예외 시 raw query로 fallback, CachedSearch로 저장."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    mock_llm = MagicMock()

    with (
        patch("catchup.search.planner.plan_manual_search.prompt_loader") as mock_loader,
        patch(
            "catchup.search.planner.plan_manual_search.ainvoke_llm_with_token_usage"
        ) as mock_invoke,
    ):
        mock_loader.get_prompt.return_value = [MagicMock()]
        mock_invoke.side_effect = Exception("LLM timeout")

        state = _make_state(original_query="fallback test")
        result = await plan_manual_search_node(state, llm=mock_llm)

    cached = result["query_cache"]["fallback test"]
    assert isinstance(cached, CachedSearch)
    assert cached.planned.query == "fallback test"
    assert cached.planned.keyword_tokens == []


@pytest.mark.asyncio
async def test_structured_output_uses_manual_search_query_schema():
    """`with_structured_output`이 ManualSearchQuery 스키마로 호출되는지 검증."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    planned = _make_planned_search()
    mock_llm = MagicMock()

    with (
        patch("catchup.search.planner.plan_manual_search.prompt_loader") as mock_loader,
        patch(
            "catchup.search.planner.plan_manual_search.ainvoke_llm_with_token_usage"
        ) as mock_invoke,
    ):
        mock_loader.get_prompt.return_value = [MagicMock()]
        mock_invoke.return_value = (
            {"parsed": planned, "raw": MagicMock()},
            {"token_breakdown": {}},
        )

        state = _make_state(original_query="query")
        await plan_manual_search_node(state, llm=mock_llm)

    mock_llm.with_structured_output.assert_called_once_with(
        ManualSearchQuery, method="function_calling", include_raw=True
    )


@pytest.mark.asyncio
async def test_prompt_loader_receives_current_time():
    """prompt_loader가 query와 current_time 인자로 호출되는지 검증."""
    from catchup.schemas.context import GlobalCurrentTimeContext
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    planned = _make_planned_search()
    mock_llm = MagicMock()

    with (
        patch("catchup.search.planner.plan_manual_search.prompt_loader") as mock_loader,
        patch(
            "catchup.search.planner.plan_manual_search.ainvoke_llm_with_token_usage"
        ) as mock_invoke,
    ):
        mock_loader.get_prompt.return_value = [MagicMock()]
        mock_invoke.return_value = (
            {"parsed": planned, "raw": MagicMock()},
            {"token_breakdown": {}},
        )

        state = _make_state(original_query="내 검색어")
        await plan_manual_search_node(state, llm=mock_llm)

    _, kwargs = mock_loader.get_prompt.call_args
    assert kwargs.get("query") == "내 검색어"
    assert isinstance(kwargs.get("current_time"), GlobalCurrentTimeContext)


@pytest.mark.asyncio
async def test_cache_hit_within_ttl_skips_llm():
    """generated_at 기준 12시간 이내면 LLM을 호출하지 않는다."""
    from datetime import datetime
    from datetime import timedelta
    from datetime import timezone

    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    recent = datetime.now(timezone.utc) - timedelta(hours=6)
    cached = CachedSearch(
        planned=_make_planned_search(), generated_at=recent
    )
    state = _make_state(
        original_query="hello", query_cache={"hello": cached}
    )
    mock_llm = MagicMock()

    result = await plan_manual_search_node(state, llm=mock_llm)

    assert result["query_cache_hit"] is True
    mock_llm.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_cache_expired_ttl_calls_llm():
    """generated_at 기준 12시간 초과 시 LLM을 재호출한다."""
    from datetime import datetime
    from datetime import timedelta
    from datetime import timezone

    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    old_time = datetime.now(timezone.utc) - timedelta(hours=13)
    cached = CachedSearch(
        planned=_make_planned_search(query="old plan"), generated_at=old_time
    )
    new_plan = _make_planned_search(query="fresh plan")
    mock_llm = MagicMock()

    with (
        patch("catchup.search.planner.plan_manual_search.prompt_loader") as mock_loader,
        patch(
            "catchup.search.planner.plan_manual_search.ainvoke_llm_with_token_usage"
        ) as mock_invoke,
    ):
        mock_loader.get_prompt.return_value = [MagicMock()]
        mock_invoke.return_value = (
            {"parsed": new_plan, "raw": MagicMock()},
            {"token_breakdown": {}},
        )

        state = _make_state(
            original_query="hello", query_cache={"hello": cached}
        )
        result = await plan_manual_search_node(state, llm=mock_llm)

    assert result["query_cache_hit"] is False
    assert result["query_cache"]["hello"].planned.query == "fresh plan"
