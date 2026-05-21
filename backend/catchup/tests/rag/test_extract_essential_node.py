# backend/catchup/tests/rag/test_extract_essential_node.py
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.messages import ToolMessage

from catchup.rag.agents.limit_extraction import EssentialDocResult


def _doc(doc_id: str) -> Document:
    return Document(
        page_content="content",
        metadata={"source": "test"},
        id=doc_id,
    )


@pytest.mark.asyncio
async def test_extracts_ids_when_structured_output_returned():
    """structured output으로 key_document_indices가 반환되면 IDs를 올바르게 추출한다."""
    from catchup.rag.agents.limit_extraction import extract_essential_node

    state = {
        "rewritten_query": "test query",
        "messages": [],
        "accumulated_docs": [_doc("id_A"), _doc("id_B"), _doc("id_C")],
        "agent_seen_doc_ids": ["id_A", "id_B", "id_C"],
    }
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_llm

    structured_response = {"parsed": EssentialDocResult(key_document_indices=[1, 3]), "raw": MagicMock()}

    with patch(
        "catchup.rag.agents.limit_extraction.ainvoke_llm_with_token_usage",
        new=AsyncMock(return_value=(structured_response, {})),
    ):
        result = await extract_essential_node(state, llm=mock_llm)

    assert "id_A" in result["essential_doc_ids"]
    assert "id_C" in result["essential_doc_ids"]
    assert "id_B" not in result["essential_doc_ids"]


@pytest.mark.asyncio
async def test_returns_empty_dict_on_llm_error():
    """LLM 호출 실패 시 빈 dict를 반환한다."""
    from catchup.rag.agents.limit_extraction import extract_essential_node

    state = {
        "rewritten_query": "test query",
        "messages": [],
        "accumulated_docs": [],
        "agent_seen_doc_ids": [],
    }
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_llm

    with patch(
        "catchup.rag.agents.limit_extraction.ainvoke_llm_with_token_usage",
        new=AsyncMock(side_effect=Exception("LLM error")),
    ):
        result = await extract_essential_node(state, llm=mock_llm)

    assert result == {}


@pytest.mark.asyncio
async def test_returns_empty_list_when_parsed_is_none():
    """LLM이 파싱 실패(parsed=None) 반환 시 essential_doc_ids가 비어있다."""
    from catchup.rag.agents.limit_extraction import extract_essential_node

    state = {
        "rewritten_query": "test query",
        "messages": [],
        "accumulated_docs": [_doc("id_A")],
        "agent_seen_doc_ids": ["id_A"],
    }
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_llm

    structured_response = {"parsed": None, "raw": MagicMock()}

    with patch(
        "catchup.rag.agents.limit_extraction.ainvoke_llm_with_token_usage",
        new=AsyncMock(return_value=(structured_response, {})),
    ):
        result = await extract_essential_node(state, llm=mock_llm)

    assert result["essential_doc_ids"] == []


@pytest.mark.asyncio
async def test_tool_message_content_embedded_in_user_message():
    """ToolMessage 내용을 plain text로 변환해 HumanMessage에 담아 전달하고 state를 수정하지 않는다."""
    from catchup.rag.agents.limit_extraction import extract_essential_node

    tool_msg = ToolMessage(content="[1] (slack) search result preview", tool_call_id="call_1")
    state = {
        "rewritten_query": "test query",
        "messages": [tool_msg],
        "accumulated_docs": [],
        "agent_seen_doc_ids": [],
    }
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_llm
    structured_response = {"parsed": EssentialDocResult(key_document_indices=[]), "raw": MagicMock()}
    captured_messages = []

    async def capture(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return structured_response, {}

    with patch(
        "catchup.rag.agents.limit_extraction.ainvoke_llm_with_token_usage",
        new=capture,
    ):
        await extract_essential_node(state, llm=mock_llm)

    # ToolMessage 객체가 아닌 HumanMessage로 변환돼야 한다 (Bedrock ValidationException 방지).
    assert not any(isinstance(m, ToolMessage) for m in captured_messages)
    user_msg = next(m for m in captured_messages if isinstance(m, HumanMessage))
    assert "search result preview" in user_msg.content
    # state["messages"]는 변경되지 않아야 한다.
    assert len(state["messages"]) == 1
