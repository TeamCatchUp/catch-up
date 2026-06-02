from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage

from catchup.agents.harness.graph import _extract_final_answer


def _state(messages: list, stop_reason: str | None = None) -> dict:
    return {"messages": messages, "stop_reason": stop_reason}


def test_extract_returns_last_ai_text_message():
    state = _state([
        SystemMessage(content="sys"),
        HumanMessage(content="go"),
        AIMessage(content="", tool_calls=[{"id": "1", "name": "t", "args": {}}]),
        ToolMessage(content="result", tool_call_id="1"),
        AIMessage(content="최종 답변입니다."),
    ])
    assert _extract_final_answer(state) == "최종 답변입니다."


def test_extract_skips_tool_call_ai_message():
    # STOP 정책 후 LLM이 tool_call을 재시도한 경우
    state = _state([
        SystemMessage(content="sys"),
        AIMessage(content="중간 답변", tool_calls=[]),
        ToolMessage(content="error", tool_call_id="1"),
        AIMessage(content="", tool_calls=[{"id": "2", "name": "t", "args": {}}]),
    ], stop_reason="Tool 'x' failed with STOP policy")
    assert _extract_final_answer(state) == "중간 답변"


def test_extract_returns_stop_reason_when_no_ai_text():
    # 모든 AIMessage가 tool_call만 있는 경우
    state = _state([
        SystemMessage(content="sys"),
        AIMessage(content="", tool_calls=[{"id": "1", "name": "t", "args": {}}]),
        ToolMessage(content="error", tool_call_id="1"),
    ], stop_reason="Tool 'x' failed with STOP policy")
    assert "[Agent stopped]" in _extract_final_answer(state)
    assert "Tool 'x' failed with STOP policy" in _extract_final_answer(state)
