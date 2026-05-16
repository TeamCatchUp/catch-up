from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from catchup.rag.nodes.doc_cache import merge_cache_node
from catchup.rag.nodes.doc_cache import prepare_cache_node
from catchup.rag.nodes.utils import build_search_history_summary
from catchup.rag.schemas.structures import PipelinePlan
from catchup.rag.schemas.structures import SearchTurnMeta


# ---------------------------------------------------------------------------
# build_search_history_summary
# ---------------------------------------------------------------------------


def test_build_search_history_summary_empty():
    assert build_search_history_summary([]) == ""


def test_build_search_history_summary_single():
    snap = SearchTurnMeta(
        turn_number=1,
        rewritten_query="CATDEV-119 티켓 담당자",
        query_topic="CATDEV-119 담당자",
        doc_ids=["id1", "id2"],
        source_distribution={"jira": 1, "github": 1},
    )
    summary = build_search_history_summary([snap])
    assert "[Search 1] (hot cache)" in summary
    assert 'Query: "CATDEV-119 티켓 담당자"' in summary
    assert "jira:1" in summary
    assert "github:1" in summary
    assert "2 docs" in summary


def test_build_search_history_summary_multiple():
    snaps = [
        SearchTurnMeta(
            turn_number=1,
            rewritten_query="query A",
            query_topic="topic A",
            doc_ids=["a1", "a2", "a3"],
            source_distribution={"jira": 2, "slack": 1},
        ),
        SearchTurnMeta(
            turn_number=3,
            rewritten_query="query B",
            query_topic="topic B",
            doc_ids=["b1", "b2"],
            source_distribution={"github": 2},
        ),
    ]
    summary = build_search_history_summary(snaps)
    lines = summary.splitlines()

    assert "[Search 1]" in summary
    assert "(hot cache)" not in summary.split("[Search 2]")[0]  # 첫 항목은 hot cache 아님
    assert "[Search 2] (hot cache)" in summary  # 마지막 항목은 hot cache

    # 연속 인덱스 사용 (turn_number=3이어도 Search 2로 표시)
    assert "[Search 3]" not in summary


# ---------------------------------------------------------------------------
# merge_cache_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_cache_node_creates_snapshot():
    docs = [
        Document(page_content="doc1", metadata={"source": "jira"}, id="id1"),
        Document(page_content="doc2", metadata={"source": "slack"}, id="id2"),
    ]
    state = {
        "retrieved_docs": docs,
        "turn_number": 2,
        "rewritten_query": "배포 이슈 원인",
        "query_topic": "배포 이슈",
        "search_turn_history": [],
    }

    result = await merge_cache_node(state)

    assert result["doc_cache"] == docs
    assert len(result["search_turn_history"]) == 1

    snap = result["search_turn_history"][0]
    assert snap.turn_number == 2
    assert snap.rewritten_query == "배포 이슈 원인"
    assert snap.query_topic == "배포 이슈"
    assert set(snap.doc_ids) == {"id1", "id2"}
    assert snap.source_distribution == {"jira": 1, "slack": 1}


@pytest.mark.asyncio
async def test_merge_cache_node_accumulates():
    existing_snap = SearchTurnMeta(
        turn_number=1,
        rewritten_query="old query",
        query_topic="old topic",
        doc_ids=["old1"],
        source_distribution={"github": 1},
    )
    docs = [Document(page_content="new", metadata={"source": "jira"}, id="new1")]
    state = {
        "retrieved_docs": docs,
        "turn_number": 3,
        "rewritten_query": "new query",
        "query_topic": "new topic",
        "search_turn_history": [existing_snap],
    }

    result = await merge_cache_node(state)

    assert len(result["search_turn_history"]) == 2
    assert result["search_turn_history"][0].turn_number == 1  # 기존 유지
    assert result["search_turn_history"][1].turn_number == 3  # 신규 추가


# ---------------------------------------------------------------------------
# prepare_cache_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_cache_node_hot_cache_only():
    """reuse_history_turn_numbers가 없으면 hot cache만 반환."""
    hot_docs = [Document(page_content="hot", metadata={}, id="h1")]
    mock_vdb = MagicMock()

    state = {
        "doc_cache": hot_docs,
        "search_turn_history": [],
        "pipeline_plan": PipelinePlan(
            pipeline_type="reuse",
            reuse_history_turn_numbers=None,
        ),
    }

    result = await prepare_cache_node(state, vector_db_service=mock_vdb)

    assert result["retrieved_docs"] == hot_docs
    mock_vdb.fetch_by_ids.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_cache_node_past_turn_only():
    """reuse_history_turn_numbers=[1]이면 Search 1만 사용, hot cache 제외."""
    hot_docs = [Document(page_content="hot", metadata={}, id="h1")]
    past_docs = [Document(page_content="past", metadata={}, id="p1")]

    snap = SearchTurnMeta(
        turn_number=1,
        rewritten_query="old query",
        query_topic=None,
        doc_ids=["p1"],
        source_distribution={"jira": 1},
    )

    mock_vdb = AsyncMock()
    mock_vdb.fetch_by_ids.return_value = past_docs

    state = {
        "doc_cache": hot_docs,
        "search_turn_history": [snap],  # Search 1 = hot cache (마지막 항목)
        "pipeline_plan": PipelinePlan(
            pipeline_type="reuse",
            reuse_history_turn_numbers=[1],  # hot cache 인덱스 = 1 → hot cache 포함
        ),
    }

    result = await prepare_cache_node(state, vector_db_service=mock_vdb)

    # Search 1이 hot cache이므로 DB fetch 없이 hot_docs 사용
    mock_vdb.fetch_by_ids.assert_not_called()
    assert result["retrieved_docs"] == hot_docs


@pytest.mark.asyncio
async def test_prepare_cache_node_past_turn_excludes_hot():
    """reuse_history_turn_numbers=[1]이 hot cache가 아닌 경우, hot cache 제외."""
    hot_docs = [Document(page_content="hot", metadata={}, id="h1")]
    past_docs = [Document(page_content="past", metadata={}, id="p1")]

    snap1 = SearchTurnMeta(
        turn_number=1,
        rewritten_query="past query",
        query_topic=None,
        doc_ids=["p1"],
        source_distribution={"jira": 1},
    )
    snap2 = SearchTurnMeta(
        turn_number=2,
        rewritten_query="hot query",
        query_topic=None,
        doc_ids=["h1"],
        source_distribution={"slack": 1},
    )

    mock_vdb = AsyncMock()
    mock_vdb.fetch_by_ids.return_value = past_docs

    state = {
        "doc_cache": hot_docs,
        "search_turn_history": [snap1, snap2],  # snap2가 hot cache (index=2)
        "pipeline_plan": PipelinePlan(
            pipeline_type="reuse",
            reuse_history_turn_numbers=[1],  # hot cache(2) 미포함 → Search 1만
        ),
    }

    result = await prepare_cache_node(state, vector_db_service=mock_vdb)

    mock_vdb.fetch_by_ids.assert_called_once_with(["p1"])
    assert len(result["retrieved_docs"]) == 1
    assert result["retrieved_docs"][0].id == "p1"  # hot cache 제외


@pytest.mark.asyncio
async def test_prepare_cache_node_past_and_hot():
    """reuse_history_turn_numbers=[1, 2]에서 2가 hot cache이면 둘 다 포함."""
    hot_docs = [Document(page_content="hot", metadata={}, id="h1")]
    past_docs = [Document(page_content="past", metadata={}, id="p1")]

    snap1 = SearchTurnMeta(
        turn_number=1, rewritten_query="q1", query_topic=None,
        doc_ids=["p1"], source_distribution={"jira": 1},
    )
    snap2 = SearchTurnMeta(
        turn_number=2, rewritten_query="q2", query_topic=None,
        doc_ids=["h1"], source_distribution={"slack": 1},
    )

    mock_vdb = AsyncMock()
    mock_vdb.fetch_by_ids.return_value = past_docs

    state = {
        "doc_cache": hot_docs,
        "search_turn_history": [snap1, snap2],
        "pipeline_plan": PipelinePlan(
            pipeline_type="reuse",
            reuse_history_turn_numbers=[1, 2],  # Search 1 + hot cache(2)
        ),
    }

    result = await prepare_cache_node(state, vector_db_service=mock_vdb)

    mock_vdb.fetch_by_ids.assert_called_once_with(["p1"])
    assert len(result["retrieved_docs"]) == 2


@pytest.mark.asyncio
async def test_prepare_cache_node_backward_compat():
    """search_turn_history가 없는 구 체크포인트는 hot cache만 반환."""
    hot_docs = [Document(page_content="hot", metadata={}, id="h1")]
    mock_vdb = MagicMock()

    state = {
        "doc_cache": hot_docs,
        # search_turn_history 키 자체가 없는 구 state
        "pipeline_plan": PipelinePlan(
            pipeline_type="reuse",
            reuse_history_turn_numbers=[1],  # 요청해도 history 없으면 무시
        ),
    }

    result = await prepare_cache_node(state, vector_db_service=mock_vdb)

    assert result["retrieved_docs"] == hot_docs
    mock_vdb.fetch_by_ids.assert_not_called()
