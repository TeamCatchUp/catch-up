from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

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

def test_build_docs_summary():
    docs = [
        Document(page_content="content 1", metadata={"source": "slack", "created_at": "2024-01-01"}),
        Document(page_content="content 2", metadata={"source": "github"}),
        Document(page_content="content 3", metadata={"source": "slack"})
    ]
    
    # 기본 요약 (max_docs=5)
    summary = build_docs_summary(docs)
    assert "총 3개 문서 수집됨" in summary
    assert "slack:2" in summary
    assert "github:1" in summary
    assert "[1] (slack)" in summary
    
    # max_docs 제한 확인
    summary_limited = build_docs_summary(docs, max_docs=1)
    assert "... 외 2개" in summary_limited
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
