from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import ToolMessage

from catchup.rag.nodes.utils import build_docs_summary
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import drop_orphaned_tool_calls
from catchup.rag.nodes.utils import get_formatted_history_text


def test_drop_orphaned_tool_calls():
    # 1. Orphaned case: AIMessage with tool_calls as last message
    msg_with_tool = AIMessage(content="", tool_calls=[{"name": "test", "args": {}, "id": "1"}])
    messages = [HumanMessage(content="hi"), msg_with_tool]
    result = drop_orphaned_tool_calls(messages)
    assert len(result) == 1
    assert isinstance(result[0], HumanMessage)

    # 2. Normal case: Last message is not AIMessage with tool_calls
    messages = [HumanMessage(content="hi"), AIMessage(content="hello")]
    result = drop_orphaned_tool_calls(messages)
    assert len(result) == 2
    assert result == messages

    # 3. Internal orphan: AIMessage(tool_calls) followed by AIMessage instead of ToolMessage
    # 실제 발생 패턴: AIMessage(G8nL) → AIMessage(V98G) → ToolMessage(V98G)
    orphan_ai = AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "G8nL"}])
    valid_ai = AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "V98G"}])
    tool_msg = ToolMessage(content="result", tool_call_id="V98G")
    stop_ai = AIMessage(content="done")
    messages = [HumanMessage(content="q"), orphan_ai, valid_ai, tool_msg, stop_ai]
    result = drop_orphaned_tool_calls(messages)
    assert len(result) == 4
    assert result[0] == HumanMessage(content="q")
    assert result[1] == valid_ai
    assert result[2] == tool_msg
    assert result[3] == stop_ai

    # 4. Valid pair: AIMessage(tool_calls) + ToolMessage → 유지
    ai_with_tool = AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "xyz"}])
    tool_msg_valid = ToolMessage(content="ok", tool_call_id="xyz")
    messages = [HumanMessage(content="q"), ai_with_tool, tool_msg_valid]
    result = drop_orphaned_tool_calls(messages)
    assert len(result) == 3

def test_build_docs_summary():
    docs = [
        Document(page_content="content 1", metadata={"source": "slack", "created_at": "2024-01-01"}),
        Document(page_content="content 2", metadata={"source": "github"}),
        Document(page_content="content 3", metadata={"source": "slack"})
    ]

    # 기본 요약 (max_docs=5)
    summary = build_docs_summary(docs)
    assert "Total 3docs accumulated" in summary
    assert "slack:2" in summary
    assert "github:1" in summary
    assert "[1] (slack)" in summary

    # max_docs 제한 확인
    summary_limited = build_docs_summary(docs, max_docs=1)
    assert "and 2 more document(s)" in summary_limited
    assert "[2]" not in summary_limited

def test_get_formatted_history_text():
    history = [
        HumanMessage(content="question"),
        AIMessage(content="answer")
    ]
    formatted = get_formatted_history_text(history)
    assert "human: question" in formatted
    assert "ai: answer" in formatted

@pytest.mark.asyncio
async def test_ainvoke_llm_with_token_usage():
    mock_llm = AsyncMock()
    mock_response = AIMessage(content="response")
    # langchain-core의 BaseMessage.usage_metadata 모사
    mock_response.usage_metadata = {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30
    }
    mock_response.response_metadata = {
        "model_id": "test-model"
    }
    mock_llm.ainvoke.return_value = mock_response
    
    messages = [HumanMessage(content="hi")]
    response, token_usages = await ainvoke_llm_with_token_usage(mock_llm, messages)
    
    assert response.content == "response"
    assert token_usages["token_breakdown"]["test-model"]["input_tokens"] == 10
    assert token_usages["token_breakdown"]["test-model"]["output_tokens"] == 20
    mock_llm.ainvoke.assert_called_once_with(input=messages)

@pytest.mark.asyncio
async def test_ainvoke_llm_with_token_usage_structured():
    mock_llm = AsyncMock()
    # with_structured_output(include_raw=True) 케이스 모사
    raw_response = AIMessage(content="raw")
    raw_response.usage_metadata = {"input_tokens": 50, "output_tokens": 0}
    raw_response.response_metadata = {"model_id": "structured-model"}
    
    mock_llm.ainvoke.return_value = {
        "parsed": MagicMock(),
        "raw": raw_response
    }
    
    response, token_usages = await ainvoke_llm_with_token_usage(mock_llm, [])
    assert response["raw"].content == "raw"
    assert token_usages["token_breakdown"]["structured-model"]["input_tokens"] == 50
