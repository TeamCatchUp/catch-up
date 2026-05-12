"""TDD Red Phase: plan_manual_search_node tests.

Written before implementation. All tests should fail initially with ImportError.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.rag.schemas.structures import VectorDbSearchQuery


def _make_state(
    original_query: str = "테스트 쿼리",
    last_planned_query: str = "",
    planned_search: VectorDbSearchQuery | None = None,
) -> dict:
    return {
        "original_query": original_query,
        "last_planned_query": last_planned_query,
        "planned_search": planned_search,
    }


def _make_planned_search(
    query: str = "semantic query in English",
    keyword_tokens: list[str] | None = None,
) -> VectorDbSearchQuery:
    return VectorDbSearchQuery(
        query=query,
        keyword_tokens=keyword_tokens or [],
        reasoning="test reasoning",
    )


@pytest.mark.asyncio
async def test_cache_hit_returns_empty_dict():
    """동일 쿼리 + plan 존재 → {} 반환, LLM 미호출."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    existing_plan = _make_planned_search()
    state = _make_state(
        original_query="hello",
        last_planned_query="hello",
        planned_search=existing_plan,
    )
    mock_llm = MagicMock()

    result = await plan_manual_search_node(state, llm=mock_llm)

    assert result == {}
    mock_llm.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_when_planned_search_is_none():
    """plan=None이면 쿼리가 동일해도 LLM 호출."""
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

        state = _make_state(
            original_query="first query",
            last_planned_query="first query",
            planned_search=None,
        )
        result = await plan_manual_search_node(state, llm=mock_llm)

    assert result["planned_search"] == planned
    assert result["last_planned_query"] == "first query"


@pytest.mark.asyncio
async def test_cache_miss_when_query_changes():
    """쿼리 변경 시 LLM 재호출, 새 plan 반환."""
    from catchup.search.planner.plan_manual_search import plan_manual_search_node

    new_plan = _make_planned_search(
        query="new English plan", keyword_tokens=["NewFeature"]
    )
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
            original_query="new query",
            last_planned_query="old query",
            planned_search=_make_planned_search(query="old English plan"),
        )
        result = await plan_manual_search_node(state, llm=mock_llm)

    assert result["last_planned_query"] == "new query"
    assert result["planned_search"].query == "new English plan"
    assert result["planned_search"].keyword_tokens == ["NewFeature"]


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_raw_query():
    """LLM 예외 시 raw query로 fallback, 예외 미발생."""
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

        state = _make_state(
            original_query="fallback test",
            last_planned_query="",
            planned_search=None,
        )
        result = await plan_manual_search_node(state, llm=mock_llm)

    assert result["planned_search"].query == "fallback test"
    assert result["planned_search"].keyword_tokens == []
    assert result["last_planned_query"] == "fallback test"


@pytest.mark.asyncio
async def test_structured_output_uses_vector_db_search_query_schema():
    """`with_structured_output`이 VectorDbSearchQuery 스키마로 호출되는지 검증."""
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

        state = _make_state(
            original_query="query", last_planned_query="", planned_search=None
        )
        await plan_manual_search_node(state, llm=mock_llm)

    mock_llm.with_structured_output.assert_called_once_with(
        VectorDbSearchQuery, method="function_calling", include_raw=True
    )


@pytest.mark.asyncio
async def test_prompt_loader_called_with_correct_key():
    """prompt_loader가 올바른 키와 query 변수로 호출되는지 검증."""
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

        state = _make_state(
            original_query="내 검색어", last_planned_query="", planned_search=None
        )
        await plan_manual_search_node(state, llm=mock_llm)

    mock_loader.get_prompt.assert_called_once_with(
        "search/plan_manual_search_node", query="내 검색어"
    )
