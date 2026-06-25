from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from catchup.automations.nodes.generate_guide import generate_guide_node
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalCurrentTimeContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext


def _make_global_context() -> GlobalContext:
    return GlobalContext(
        user=GlobalUserContext(id=1, name="테스터", email="test@example.com", department="CS"),
        workspace=GlobalWorkspaceContext(id=1, name="테스트 워크스페이스"),
        company=GlobalCompanyContext(id=1, name="테스트 컴퍼니"),
        current_time=GlobalCurrentTimeContext(),
    )


def _make_state(docs: list[Document]) -> dict:
    return {
        "inquiry_text": "환불 신청은 어떻게 하나요?",
        "retrieved_docs": docs,
        "rewritten_query": "환불 신청 방법",
        "global_context": _make_global_context(),
    }


@pytest.mark.asyncio
async def test_generate_guide_node_returns_guide_text():
    """LLM 응답이 guide_text로 state에 저장된다."""
    docs = [Document(page_content="환불은 마이페이지 > 주문내역에서 신청 가능합니다.", id="d1")]
    state = _make_state(docs)

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="마이페이지 > 주문내역에서 환불 신청 버튼을 안내하세요.")
    )

    with patch(
        "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ):
        result = await generate_guide_node(state, llm=mock_llm)

    assert result["guide_text"] == "마이페이지 > 주문내역에서 환불 신청 버튼을 안내하세요."


@pytest.mark.asyncio
async def test_generate_guide_node_passes_guide_instruction_to_prompt():
    """guide_instruction이 있으면 prompt_loader에 전달된다."""
    docs = [Document(page_content="환불 정책 내용", id="d1")]
    state = {
        **_make_state(docs),
        "guide_instruction": "결제 문의는 영수증을 먼저 요청하세요.",
    }

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="가이드"))

    with patch(
        "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ) as mock_get_prompt:
        await generate_guide_node(state, llm=mock_llm)

    _, kwargs = mock_get_prompt.call_args
    assert kwargs.get("guide_instruction") == "결제 문의는 영수증을 먼저 요청하세요."


@pytest.mark.asyncio
async def test_generate_guide_node_no_docs_returns_fallback():
    """문서가 없으면 fallback 가이드를 반환한다."""
    state = _make_state([])

    mock_llm = MagicMock()

    result = await generate_guide_node(state, llm=mock_llm)

    mock_llm.ainvoke.assert_not_called()
    assert result["guide_text"] is not None
    assert len(result["guide_text"]) > 0
