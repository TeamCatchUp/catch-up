from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.automations.nodes.generate_guide import generate_guide_node
from catchup.automations.structures import GuideDraft
from catchup.schemas.context import GlobalCompanyContext
from catchup.schemas.context import GlobalContext
from catchup.schemas.context import GlobalCurrentTimeContext
from catchup.schemas.context import GlobalUserContext
from catchup.schemas.context import GlobalWorkspaceContext


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


def _make_structured_llm(guide_draft: GuideDraft) -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=guide_draft)
    return mock_llm


@pytest.mark.asyncio
async def test_generate_guide_node_returns_structured_fields():
    """LLM structured output이 guide_text/guide_explanation/citations로 state에 분리 저장된다."""
    docs = [
        Document(
            page_content="환불은 마이페이지 > 주문내역에서 신청 가능합니다.",
            id="d1",
            metadata={"source": "channel_talk"},
        )
    ]
    state = _make_state(docs)

    guide_draft = GuideDraft(
        draft="마이페이지 > 주문내역에서 환불 신청 버튼을 눌러주세요.",
        explanation="환불 절차를 안내하는 표준 답변입니다.",
        cited_indices=[1],
    )
    mock_llm = _make_structured_llm(guide_draft)

    with patch(
        "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ):
        result = await generate_guide_node(state, llm=mock_llm)

    assert result["guide_text"] == guide_draft.draft
    assert result["guide_explanation"] == guide_draft.explanation
    assert len(result["citations"]) == 1
    assert result["citations"][0].is_cited is True


@pytest.mark.asyncio
async def test_generate_guide_node_falls_back_when_no_indices_cited():
    """cited_indices가 비어 있으면 앞에서부터 최대 개수만큼 citations로 폴백한다."""
    docs = [
        Document(page_content=f"문서 {i}", id=f"d{i}", metadata={"source": "channel_talk"})
        for i in range(3)
    ]
    state = _make_state(docs)

    guide_draft = GuideDraft(draft="답변", explanation="설명", cited_indices=[])
    mock_llm = _make_structured_llm(guide_draft)

    with patch(
        "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ):
        result = await generate_guide_node(state, llm=mock_llm)

    assert len(result["citations"]) == 3


@pytest.mark.asyncio
async def test_generate_guide_node_passes_guide_instruction_to_prompt():
    """guide_instruction이 있으면 prompt_loader에 전달된다."""
    docs = [Document(page_content="환불 정책 내용", id="d1", metadata={"source": "channel_talk"})]
    state = {
        **_make_state(docs),
        "guide_instruction": "결제 문의는 영수증을 먼저 요청하세요.",
    }

    mock_llm = _make_structured_llm(
        GuideDraft(draft="가이드", explanation="설명", cited_indices=[])
    )

    with patch(
        "catchup.automations.nodes.generate_guide.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ) as mock_get_prompt:
        await generate_guide_node(state, llm=mock_llm)

    _, kwargs = mock_get_prompt.call_args
    assert kwargs.get("guide_instruction") == "결제 문의는 영수증을 먼저 요청하세요."


@pytest.mark.asyncio
async def test_generate_guide_node_no_docs_returns_fallback():
    """문서가 없으면 draft는 비우고 explanation에 에스컬레이션 안내를 담아 반환한다."""
    state = _make_state([])

    mock_llm = MagicMock()

    result = await generate_guide_node(state, llm=mock_llm)

    mock_llm.with_structured_output.assert_not_called()
    assert result["guide_text"] == ""
    assert len(result["guide_explanation"]) > 0
    assert result["citations"] == []
