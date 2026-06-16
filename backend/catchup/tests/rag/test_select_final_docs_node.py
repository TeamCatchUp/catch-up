from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.rag.nodes.rerank.final_doc_selection import select_final_docs_node
from catchup.rag.nodes.utils import get_document_id


def _doc(doc_id: str, score: float = 0.5) -> Document:
    return Document(
        page_content=f"content {doc_id}",
        metadata={"relevance_score": score, "source": "test"},
        id=doc_id,
    )


def _ids(docs: list[Document]) -> list[str]:
    return [get_document_id(d) for d in docs]


@pytest.mark.asyncio
async def test_select_final_docs_node_slices_to_simple_k():
    """max_pipeline_type=simple이면 retrieved_docs를 10개로 자른다."""
    docs = [_doc(f"d{i}", score=1.0 - i * 0.05) for i in range(20)]
    state = {
        "retrieved_docs": docs,
        "rewritten_query": "테스트 쿼리",
        "max_pipeline_type": "simple",
        "pipeline_plan": None,
        "essential_doc_ids": [],
        "agent_seen_doc_ids": [],
        "agent_stop_reason": None,
    }

    with patch(
        "catchup.rag.nodes.rerank.final_doc_selection.adispatch_custom_event",
        new_callable=AsyncMock,
    ):
        result = await select_final_docs_node(state)

    assert len(result["retrieved_docs"]) == 10
    assert result["rerank_metadata"]["bypass_count"] == 0


@pytest.mark.asyncio
async def test_select_final_docs_node_essential_bypass():
    """essential_doc_ids에 포함된 문서가 reranker top-K 밖에 있어도 포함된다."""
    docs = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(15)]
    essential = _doc("e1", score=0.01)
    docs.append(essential)

    state = {
        "retrieved_docs": docs,
        "rewritten_query": "테스트 쿼리",
        "max_pipeline_type": "simple",
        "pipeline_plan": None,
        "essential_doc_ids": ["e1"],
        "agent_seen_doc_ids": [],
        "agent_stop_reason": None,
    }

    with patch(
        "catchup.rag.nodes.rerank.final_doc_selection.adispatch_custom_event",
        new_callable=AsyncMock,
    ):
        result = await select_final_docs_node(state)

    final_ids = _ids(result["retrieved_docs"])
    assert "e1" in final_ids
    assert len(result["retrieved_docs"]) == 10
    assert result["rerank_metadata"]["bypass_count"] == 1


@pytest.mark.asyncio
async def test_select_final_docs_node_empty_docs():
    """retrieved_docs가 비어있으면 빈 결과를 반환한다."""
    state = {
        "retrieved_docs": [],
        "rewritten_query": "테스트 쿼리",
        "max_pipeline_type": "simple",
        "pipeline_plan": None,
        "essential_doc_ids": [],
        "agent_seen_doc_ids": [],
        "agent_stop_reason": None,
    }

    with patch(
        "catchup.rag.nodes.rerank.final_doc_selection.adispatch_custom_event",
        new_callable=AsyncMock,
    ):
        result = await select_final_docs_node(state)

    assert result["retrieved_docs"] == []
    assert result["confirmed_essential_doc_ids"] == []


@pytest.mark.asyncio
async def test_select_final_docs_node_confirmed_essential_tracking():
    """essential 문서가 final_docs에 포함되면 confirmed_essential_doc_ids에 기록된다."""
    docs = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(5)]
    essential = docs[2]
    essential_id = get_document_id(essential)

    state = {
        "retrieved_docs": docs,
        "rewritten_query": "테스트",
        "max_pipeline_type": "simple",
        "pipeline_plan": None,
        "essential_doc_ids": [essential_id],
        "agent_seen_doc_ids": [],
        "agent_stop_reason": None,
    }

    with patch(
        "catchup.rag.nodes.rerank.final_doc_selection.adispatch_custom_event",
        new_callable=AsyncMock,
    ):
        result = await select_final_docs_node(state)

    assert essential_id in result["confirmed_essential_doc_ids"]
