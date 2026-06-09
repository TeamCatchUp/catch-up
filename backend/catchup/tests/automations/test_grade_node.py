from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.automations.nodes.grade import grade_node


def _make_state(docs: list[Document]) -> dict:
    return {
        "inquiry_text": "결제가 안 돼요",
        "retrieved_docs": docs,
        "rewritten_query": "결제가 안 돼요",
    }


def _doc(content: str, doc_id: str = "d1") -> Document:
    return Document(page_content=content, id=doc_id)


@pytest.mark.asyncio
async def test_grade_node_reusable_true():
    """LLM이 reusable=True를 반환하면 state에 그대로 반영된다."""
    docs = [_doc("카드 결제 오류 시 설정 초기화 후 재시도하면 해결됩니다.")]
    state = _make_state(docs)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value={"reusable": True, "reason": "해결 방법이 명확하게 포함됨"}
    )

    with patch(
        "catchup.automations.nodes.grade.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ):
        result = await grade_node(state, llm=mock_llm)

    assert result["grade_result"]["reusable"] is True
    assert "reason" in result["grade_result"]


@pytest.mark.asyncio
async def test_grade_node_reusable_false():
    """LLM이 reusable=False를 반환하면 state에 그대로 반영된다."""
    docs = [_doc("일반적인 문의 내용입니다.")]
    state = _make_state(docs)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value={"reusable": False, "reason": "구체적 해결 방법 없음"}
    )

    with patch(
        "catchup.automations.nodes.grade.prompt_loader.get_prompt",
        return_value=[MagicMock()],
    ):
        result = await grade_node(state, llm=mock_llm)

    assert result["grade_result"]["reusable"] is False


@pytest.mark.asyncio
async def test_grade_node_empty_docs():
    """문서가 없으면 LLM을 호출하지 않고 reusable=False를 반환한다."""
    state = _make_state([])

    mock_llm = MagicMock()

    result = await grade_node(state, llm=mock_llm)

    mock_llm.with_structured_output.assert_not_called()
    assert result["grade_result"]["reusable"] is False
    assert "reason" in result["grade_result"]
