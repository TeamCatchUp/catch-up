from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.rag.schemas.structures import PipelinePlan


def _make_state(agent_iteration: int, retrieved_docs: list) -> dict:
    return {
        "original_query": "테스트 질문",
        "rewritten_query": "테스트 질문",
        "agent_iteration": agent_iteration,
        "accumulated_docs": [],
        "retrieved_docs": retrieved_docs,
        "messages": [],
        "pipeline_plan": PipelinePlan(pipeline_type="standard", max_iterations=4),
        "global_context": MagicMock(model_dump=lambda: {}),
        "agent_seen_doc_ids": [],
    }


@pytest.mark.asyncio
async def test_iter0_passes_cached_docs_to_prompt():
    """iter 0에서 retrieved_docs가 있으면 cached_docs_summary가 프롬프트에 포함된다."""
    captured_kwargs = {}

    def fake_get_prompt(name, **kwargs):
        captured_kwargs.update(kwargs)
        return "system prompt"

    docs = [Document(page_content="캐시된 문서 내용", metadata={"source": "github"}, id="d1")]
    state = _make_state(agent_iteration=0, retrieved_docs=docs)

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_response = MagicMock(tool_calls=[], content="답변")

    with patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", side_effect=fake_get_prompt):
        with patch("catchup.rag.agents.standard_agent.ainvoke_llm_with_token_usage", new_callable=AsyncMock) as mock_invoke:
            with patch("catchup.rag.agents.standard_agent.adispatch_custom_event", new_callable=AsyncMock):
                mock_invoke.return_value = (mock_response, {"token_breakdown": {}})
                await standard_agent_node(state, llm=mock_llm)

    assert "cached_docs_summary" in captured_kwargs
    assert "캐시된 문서 내용" in captured_kwargs["cached_docs_summary"]


@pytest.mark.asyncio
async def test_iter1_does_not_pass_cached_docs():
    """iter 1 이상에서는 retrieved_docs를 프롬프트에 포함하지 않는다."""
    captured_kwargs = {}

    def fake_get_prompt(name, **kwargs):
        captured_kwargs.update(kwargs)
        return "system prompt"

    docs = [Document(page_content="캐시된 문서", metadata={"source": "github"}, id="d1")]
    state = _make_state(agent_iteration=1, retrieved_docs=docs)

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_response = MagicMock(tool_calls=[], content="답변")

    with patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", side_effect=fake_get_prompt):
        with patch("catchup.rag.agents.standard_agent.ainvoke_llm_with_token_usage", new_callable=AsyncMock) as mock_invoke:
            with patch("catchup.rag.agents.standard_agent.adispatch_custom_event", new_callable=AsyncMock):
                mock_invoke.return_value = (mock_response, {"token_breakdown": {}})
                await standard_agent_node(state, llm=mock_llm)

    assert captured_kwargs.get("cached_docs_summary", "") == ""
