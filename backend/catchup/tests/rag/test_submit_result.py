from langchain_core.documents import Document

from catchup.rag.agents.tools.search_tools import REACT_TOOLS
from catchup.rag.nodes.utils import map_indices_to_doc_ids


def _doc(doc_id: str) -> Document:
    return Document(page_content="content", metadata={"source": "github"}, id=doc_id)


def test_submit_result_in_react_tools():
    names = [t.name for t in REACT_TOOLS]
    assert "submit_result" in names


def test_submit_result_schema_has_required_fields():
    tool = next(t for t in REACT_TOOLS if t.name == "submit_result")
    schema = tool.args_schema.schema()
    props = schema["properties"]
    assert "key_document_indices" in props
    assert "key_documents" in props
    assert "search_coverage" in props
    assert "reason_for_stopping" in props


def test_map_indices_to_doc_ids_basic():
    docs = [_doc("id_A"), _doc("id_B"), _doc("id_C")]
    result = map_indices_to_doc_ids([1, 3], docs, [])
    assert result == {"id_A", "id_C"}


def test_map_indices_to_doc_ids_uses_agent_seen_order():
    """agent_seen_ids 순서 기준으로 매핑해야 한다 (accumulated_docs 삽입 순서 아님)."""
    doc_a = _doc("id_A")
    doc_b = _doc("id_B")
    doc_c = _doc("id_C")
    accumulated = [doc_c, doc_a, doc_b]        # 삽입 순서
    agent_seen = ["id_A", "id_B", "id_C"]      # 노출 순서
    result = map_indices_to_doc_ids([1, 2], accumulated, agent_seen)
    assert result == {"id_A", "id_B"}          # seen 순서 기준 [1]=A, [2]=B


def test_map_indices_out_of_range_ignored():
    docs = [_doc("id_A")]
    result = map_indices_to_doc_ids([1, 99], docs, [])
    assert result == {"id_A"}  # 99 무시


def test_map_indices_empty():
    assert map_indices_to_doc_ids([], [], []) == set()


from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.rag.schemas.structures import PipelinePlan


def _make_state(agent_iteration: int = 0, accumulated_docs=None, agent_seen_ids=None) -> dict:
    return {
        "original_query": "테스트 질문",
        "rewritten_query": "테스트 질문",
        "agent_iteration": agent_iteration,
        "accumulated_docs": accumulated_docs or [],
        "retrieved_docs": [],
        "messages": [],
        "pipeline_plan": PipelinePlan(pipeline_type="standard", max_iterations=4),
        "global_context": MagicMock(model_dump=lambda: {}),
        "agent_seen_doc_ids": agent_seen_ids or [],
    }


@pytest.mark.asyncio
async def test_submit_result_sets_state_correctly():
    """submit_result tool call이 essential_doc_ids와 agent_reasoning을 올바르게 설정한다."""
    docs = [
        Document(page_content="doc1", metadata={"source": "github"}, id="id_A"),
        Document(page_content="doc2", metadata={"source": "slack"}, id="id_B"),
    ]
    state = _make_state(accumulated_docs=docs, agent_seen_ids=["id_A", "id_B"])

    mock_response = MagicMock()
    mock_response.tool_calls = [{
        "name": "submit_result",
        "args": {
            "key_document_indices": [1, 2],
            "key_documents": ["doc A", "doc B"],
            "search_coverage": ["항목 1"],
            "reason_for_stopping": "정보가 충분히 수집됐어요.",
        },
        "id": "call_123",
    }]
    mock_response.content = ""

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm

    with patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="system"):
        with patch("catchup.rag.agents.standard_agent.ainvoke_llm_with_token_usage", new_callable=AsyncMock) as mock_invoke:
            with patch("catchup.rag.agents.standard_agent.adispatch_custom_event", new_callable=AsyncMock):
                mock_invoke.return_value = (mock_response, {"token_breakdown": {}})
                result = await standard_agent_node(state, llm=mock_llm)

    assert result["agent_stop_reason"] == "by_choice"
    assert "정보가 충분히 수집됐어요." in result["agent_reasoning"]
    assert "doc A" in result["agent_reasoning"]
    assert "항목 1" in result["agent_reasoning"]
    assert set(result["essential_doc_ids"]) == {"id_A", "id_B"}
    assert "messages" not in result


@pytest.mark.asyncio
async def test_submit_result_does_not_add_messages():
    """submit_result 후 state.messages가 업데이트되지 않아야 한다."""
    state = _make_state()
    mock_response = MagicMock()
    mock_response.tool_calls = [{
        "name": "submit_result",
        "args": {
            "key_document_indices": [],
            "key_documents": [],
            "search_coverage": [],
            "reason_for_stopping": "포화 상태예요.",
        },
        "id": "call_456",
    }]
    mock_response.content = ""

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm

    with patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="system"):
        with patch("catchup.rag.agents.standard_agent.ainvoke_llm_with_token_usage", new_callable=AsyncMock) as mock_invoke:
            with patch("catchup.rag.agents.standard_agent.adispatch_custom_event", new_callable=AsyncMock):
                mock_invoke.return_value = (mock_response, {"token_breakdown": {}})
                result = await standard_agent_node(state, llm=mock_llm)

    assert "messages" not in result
    assert result["agent_stop_reason"] == "by_choice"


from catchup.rag.schemas.structures import PipelinePlan as _PipelinePlan
from catchup.rag.subgraphs.standard_react import _route_after_agent


def _route_state(agent_stop_reason=None, tool_calls=None, agent_iteration=0, max_iterations=4):
    from langchain_core.messages import AIMessage
    msgs = []
    if tool_calls is not None:
        ai = AIMessage(content="", tool_calls=tool_calls)
        msgs = [ai]
    return {
        "messages": msgs,
        "agent_stop_reason": agent_stop_reason,
        "agent_iteration": agent_iteration,
        "pipeline_plan": _PipelinePlan(pipeline_type="standard", max_iterations=max_iterations),
    }


def test_route_by_choice_goes_to_collect_docs():
    state = _route_state(agent_stop_reason="by_choice")
    assert _route_after_agent(state) == "collect_docs"


def test_route_search_tool_calls_goes_to_executor():
    tc = [{"name": "single_query_search", "args": {}, "id": "c1"}]
    state = _route_state(tool_calls=tc)
    assert _route_after_agent(state) == "tool_executor"


def test_route_iteration_limit_goes_to_extract_essential():
    state = _route_state(agent_iteration=4, max_iterations=4)
    assert _route_after_agent(state) == "extract_essential"


def test_route_no_tool_calls_goes_to_collect_docs():
    state = _route_state()
    assert _route_after_agent(state) == "collect_docs"
