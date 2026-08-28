from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from catchup.automations.runner import AutomationInput
from catchup.automations.runner import run_inquiry_automation
from catchup.schemas.context import GlobalCompanyContext
from catchup.schemas.context import GlobalContext
from catchup.schemas.context import GlobalCurrentTimeContext
from catchup.schemas.context import GlobalUserContext
from catchup.schemas.context import GlobalWorkspaceContext
from catchup.schemas.sources import UnknownSource


def _make_automation_input() -> AutomationInput:
    return AutomationInput(
        inquiry_text="환불 방법 문의",
        channel_talk_channel_id="channel-001",
        user_chat_id="chat-001",
        slack_channel_id="C123456",
        slack_credential_id=1,
        global_context=GlobalContext(
            user=GlobalUserContext(
                id=1, name="테스터", email="test@example.com", department="CS"
            ),
            workspace=GlobalWorkspaceContext(id=1, name="워크스페이스"),
            company=GlobalCompanyContext(id=1, name="컴퍼니"),
            current_time=GlobalCurrentTimeContext(),
        ),
    )


def _patch_graph(
    guide_text: str = "가이드 답변",
    guide_explanation: str = "설명",
):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "guide_text": guide_text,
            "guide_explanation": guide_explanation,
            "citations": [],
        }
    )
    return patch(
        "catchup.automations.runner.get_inquiry_automation_graph",
        return_value=mock_graph,
    ), mock_graph


@pytest.mark.asyncio
async def test_run_inquiry_automation_without_langfuse_skips_tracing():
    """langfuse client가 없으면 트레이싱 관련 호출 없이 그래프만 실행한다."""
    patcher, mock_graph = _patch_graph()

    with patcher, patch(
        "catchup.automations.runner.get_langfuse_client", return_value=None
    ), patch("catchup.automations.runner.CallbackHandler") as mock_handler, patch(
        "catchup.automations.runner.propagate_attributes"
    ) as mock_propagate:
        await run_inquiry_automation(_make_automation_input())

    mock_graph.ainvoke.assert_awaited_once()
    state = mock_graph.ainvoke.await_args.args[0]
    assert state["channel_talk_channel_id"] == "channel-001"
    _, kwargs = mock_graph.ainvoke.await_args
    assert kwargs["config"] == {}
    mock_handler.assert_not_called()
    mock_propagate.assert_not_called()


@pytest.mark.asyncio
async def test_run_inquiry_automation_with_langfuse_records_trace():
    """langfuse client가 있으면 callback 주입, 태깅, span 기록, flush가 모두 실행된다."""
    patcher, mock_graph = _patch_graph(
        guide_text="환불은 7일 이내 가능합니다.",
        guide_explanation="환불 규정에 따른 표준 안내입니다.",
    )
    mock_client = MagicMock()
    mock_client.get_current_trace_id.return_value = "trace-123"
    automation_input = _make_automation_input()

    with patcher, patch(
        "catchup.automations.runner.get_langfuse_client", return_value=mock_client
    ), patch("catchup.automations.runner.CallbackHandler") as mock_handler:
        result = await run_inquiry_automation(automation_input)

    mock_graph.ainvoke.assert_awaited_once()
    _, kwargs = mock_graph.ainvoke.await_args
    assert kwargs["config"]["callbacks"] == [mock_handler.return_value]

    expected_output = {
        "guide_text": "환불은 7일 이내 가능합니다.",
        "guide_explanation": "환불 규정에 따른 표준 안내입니다.",
        "citations": [],
    }
    mock_client.update_current_span.assert_called_once_with(
        input={"inquiry_text": automation_input.inquiry_text},
        output=expected_output,
    )
    mock_client.flush.assert_called_once()
    assert result == expected_output


@pytest.mark.asyncio
async def test_run_inquiry_automation_serializes_citations():
    """citations의 BaseSource 인스턴스가 JSON 직렬화된 dict로 변환되어 반환된다."""
    citation = UnknownSource(
        id="d1",
        entity_type="comment",
        title="테스트 문서",
        text="본문",
        index=1,
        is_cited=True,
    )
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "guide_text": "초안",
            "guide_explanation": "설명",
            "citations": [citation],
        }
    )

    with patch(
        "catchup.automations.runner.get_inquiry_automation_graph",
        return_value=mock_graph,
    ), patch("catchup.automations.runner.get_langfuse_client", return_value=None):
        result = await run_inquiry_automation(_make_automation_input())

    assert result["citations"] == [citation.model_dump(mode="json")]


@pytest.mark.asyncio
async def test_run_inquiry_automation_survives_langfuse_failures():
    """langfuse 호출이 전부 실패해도 그래프 실행과 완료는 영향받지 않는다."""
    patcher, mock_graph = _patch_graph()
    mock_client = MagicMock()
    mock_client.get_current_trace_id.side_effect = RuntimeError("trace id boom")
    mock_client.update_current_span.side_effect = RuntimeError("span boom")
    mock_client.flush.side_effect = RuntimeError("flush boom")

    with patcher, patch(
        "catchup.automations.runner.get_langfuse_client", return_value=mock_client
    ), patch(
        "catchup.automations.runner.propagate_attributes",
        side_effect=RuntimeError("propagate boom"),
    ):
        await run_inquiry_automation(_make_automation_input())

    mock_graph.ainvoke.assert_awaited_once()
