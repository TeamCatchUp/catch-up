"""
multi_query_search 실행 시 요청 간 중복 키워드 제거 로직 검증.

search_tool_executor_node가 multi_query_search tool call을 처리할 때,
앞선 요청에서 이미 사용된 keyword_tokens은 이후 요청에서 제거되어야 한다.
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.rag.agents.tools.search_tools import search_tool_executor_node


def _make_ai_message(tool_calls: list[dict]):
    msg = MagicMock()
    msg.tool_calls = tool_calls
    return msg


def _make_state(tool_calls: list[dict]) -> dict:
    return {
        "messages": [_make_ai_message(tool_calls)],
        "tool_filters": [],
        "accumulated_docs": [],
        "agent_seen_doc_ids": [],
    }


def _multi_query_call(search_requests: list[dict]) -> dict:
    return {
        "name": "multi_query_search",
        "args": {"reason": "test", "search_requests": search_requests},
        "id": "call-test",
    }


@pytest.fixture
def vector_db_service():
    captured: list[dict] = []

    async def fake_batch(queries, **kwargs):
        captured.extend(queries)
        return [[] for _ in queries]

    svc = MagicMock()
    svc.hybrid_search_batch = fake_batch
    svc._captured = captured
    return svc


@pytest.mark.asyncio
async def test_duplicate_keyword_removed_from_later_query(vector_db_service):
    """query1: ['A','B'], query2: ['A','C'] → query2는 ['C']만 전달되어야 한다."""
    tool_call = _multi_query_call([
        {"query": "q1", "keyword_tokens": ["A", "B"]},
        {"query": "q2", "keyword_tokens": ["A", "C"]},
    ])

    with patch("catchup.rag.agents.tools.search_tools.adispatch_custom_event", new_callable=AsyncMock):
        await search_tool_executor_node(_make_state([tool_call]), vector_db_service)

    captured = vector_db_service._captured
    assert set(captured[0]["keyword_tokens"]) == {"A", "B"}
    assert captured[1]["keyword_tokens"] == ["C"]


@pytest.mark.asyncio
async def test_all_keywords_already_used(vector_db_service):
    """query2의 키워드가 모두 query1과 겹치면 빈 리스트로 전달되어야 한다."""
    tool_call = _multi_query_call([
        {"query": "q1", "keyword_tokens": ["A", "B"]},
        {"query": "q2", "keyword_tokens": ["A", "B"]},
    ])

    with patch("catchup.rag.agents.tools.search_tools.adispatch_custom_event", new_callable=AsyncMock):
        await search_tool_executor_node(_make_state([tool_call]), vector_db_service)

    captured = vector_db_service._captured
    assert captured[1]["keyword_tokens"] == []


@pytest.mark.asyncio
async def test_no_overlap_all_keywords_preserved(vector_db_service):
    """키워드가 겹치지 않으면 양쪽 모두 그대로 유지되어야 한다."""
    tool_call = _multi_query_call([
        {"query": "q1", "keyword_tokens": ["A", "B"]},
        {"query": "q2", "keyword_tokens": ["C", "D"]},
    ])

    with patch("catchup.rag.agents.tools.search_tools.adispatch_custom_event", new_callable=AsyncMock):
        await search_tool_executor_node(_make_state([tool_call]), vector_db_service)

    captured = vector_db_service._captured
    assert set(captured[0]["keyword_tokens"]) == {"A", "B"}
    assert set(captured[1]["keyword_tokens"]) == {"C", "D"}


@pytest.mark.asyncio
async def test_empty_keywords_pass_through(vector_db_service):
    """키워드 없는 요청은 빈 리스트로 통과되고, 이후 요청 키워드에 영향을 주지 않는다."""
    tool_call = _multi_query_call([
        {"query": "q1", "keyword_tokens": []},
        {"query": "q2", "keyword_tokens": ["A"]},
    ])

    with patch("catchup.rag.agents.tools.search_tools.adispatch_custom_event", new_callable=AsyncMock):
        await search_tool_executor_node(_make_state([tool_call]), vector_db_service)

    captured = vector_db_service._captured
    assert captured[0]["keyword_tokens"] == []
    assert captured[1]["keyword_tokens"] == ["A"]


@pytest.mark.asyncio
async def test_three_queries_cumulative_dedup(vector_db_service):
    """세 쿼리에 걸쳐 누적 dedup이 올바르게 적용되어야 한다."""
    tool_call = _multi_query_call([
        {"query": "q1", "keyword_tokens": ["A", "B"]},
        {"query": "q2", "keyword_tokens": ["B", "C"]},
        {"query": "q3", "keyword_tokens": ["A", "C", "D"]},
    ])

    with patch("catchup.rag.agents.tools.search_tools.adispatch_custom_event", new_callable=AsyncMock):
        await search_tool_executor_node(_make_state([tool_call]), vector_db_service)

    captured = vector_db_service._captured
    assert set(captured[0]["keyword_tokens"]) == {"A", "B"}
    assert captured[1]["keyword_tokens"] == ["C"]   # B 제거
    assert captured[2]["keyword_tokens"] == ["D"]   # A, C 제거
