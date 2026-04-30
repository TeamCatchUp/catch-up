import asyncio
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage


@pytest.mark.asyncio
async def test_ainvoke_llm_timeout_triggers():
    """ainvoke_llm_with_token_usage가 timeout 발생 시 asyncio.TimeoutError를 re-raise하는지 검증"""
    mock_llm = MagicMock()
    
    async def long_running_task(*args, **kwargs):
        await asyncio.sleep(100)
        return MagicMock()

    # 100초 동안 대기하는 mock ainvoke
    mock_llm.ainvoke = AsyncMock(side_effect=long_running_task)
    
    messages = [HumanMessage(content="Hello")]
    
    # 0.1초 타임아웃 설정
    with pytest.raises(asyncio.TimeoutError):
        await ainvoke_llm_with_token_usage(
            llm=mock_llm,
            messages=messages,
            timeout=0.1
        )

@pytest.mark.asyncio
async def test_ainvoke_llm_no_timeout_passes():
    """타임아웃 이내에 응답이 오면 정상적으로 결과를 반환하는지 검증"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "I am fine."
    mock_response.response_metadata = {}
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    messages = [HumanMessage(content="Hello")]
    
    response, token_usages = await ainvoke_llm_with_token_usage(
        llm=mock_llm,
        messages=messages,
        timeout=5.0
    )
    
    assert response.content == "I am fine."
    mock_llm.ainvoke.assert_called_once()
