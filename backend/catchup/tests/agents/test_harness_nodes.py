import asyncio
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END

from catchup.agents.enums import FailurePolicy
from catchup.agents.harness.nodes import _execute_with_policy
from catchup.agents.harness.nodes import tool_executor_node
from catchup.agents.harness.nodes import tool_gate
from catchup.agents.schemas import ToolSpec


def _make_tool(*, return_value="ok", side_effect=None) -> StructuredTool:
    tool = MagicMock(spec=StructuredTool)
    tool.ainvoke = AsyncMock(return_value=return_value, side_effect=side_effect)
    return tool


def _make_spec(
    name: str = "catchup_kb.search",
    failure_policy: FailurePolicy = FailurePolicy.SKIP,
    max_retry: int | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        failure_policy=failure_policy,
        max_retry=max_retry,
    )


def _make_state(
    tool_calls: list[dict],
    allowed_tool_names: list[str] | None = None,
    stop_reason: str | None = None,
) -> dict:
    return {
        "messages": [
            AIMessage(content="", tool_calls=tool_calls),
        ],
        "allowed_tool_names": allowed_tool_names or [],
        "stop_reason": stop_reason,
    }


# === _execute_with_policy ===


@pytest.mark.asyncio
async def test_execute_with_policy_success_returns_content():
    tool = _make_tool(return_value="검색 결과")
    spec = _make_spec()
    content, should_stop = await _execute_with_policy(tool, {}, spec)
    assert content == "검색 결과"
    assert should_stop is False


@pytest.mark.asyncio
async def test_execute_with_policy_skip_hides_error_from_llm():
    tool = _make_tool(side_effect=ValueError("api error"))
    spec = _make_spec(failure_policy=FailurePolicy.SKIP)
    content, should_stop = await _execute_with_policy(tool, {}, spec)
    assert content == ""
    assert should_stop is False


@pytest.mark.asyncio
async def test_execute_with_policy_continue_surfaces_error():
    tool = _make_tool(side_effect=ValueError("api error"))
    spec = _make_spec(failure_policy=FailurePolicy.CONTINUE)
    content, should_stop = await _execute_with_policy(tool, {}, spec)
    assert "api error" in content
    assert should_stop is False


@pytest.mark.asyncio
async def test_execute_with_policy_stop_surfaces_error_and_signals_stop():
    tool = _make_tool(side_effect=ValueError("api error"))
    spec = _make_spec(failure_policy=FailurePolicy.STOP)
    content, should_stop = await _execute_with_policy(tool, {}, spec)
    assert "api error" in content
    assert should_stop is True


@pytest.mark.asyncio
async def test_execute_with_policy_retries_on_timeout():
    tool = _make_tool(side_effect=[asyncio.TimeoutError(), "재시도 성공"])
    spec = _make_spec(failure_policy=FailurePolicy.CONTINUE, max_retry=1)
    with patch("catchup.agents.harness.nodes.asyncio.sleep"):
        content, should_stop = await _execute_with_policy(tool, {}, spec)
    assert content == "재시도 성공"
    assert should_stop is False
    assert tool.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_execute_with_policy_non_retryable_skips_retry():
    tool = _make_tool(side_effect=ValueError("400 bad request"))
    spec = _make_spec(failure_policy=FailurePolicy.CONTINUE, max_retry=2)
    content, should_stop = await _execute_with_policy(tool, {}, spec)
    assert tool.ainvoke.call_count == 1  # 재시도 없이 즉시 정책 분기


# === tool_executor_node ===


@pytest.mark.asyncio
async def test_tool_executor_node_returns_tool_message_on_success():
    tool = _make_tool(return_value="검색 결과")
    spec = _make_spec()
    state = _make_state(
        tool_calls=[{"id": "call_1", "name": "catchup_kb__search", "args": {}}],
        allowed_tool_names=["catchup_kb.search"],
    )
    result = await tool_executor_node(
        state,
        lc_tool_map={"catchup_kb__search": tool},
        tool_spec_map={"catchup_kb.search": spec},
    )
    assert result["stop_reason"] is None
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == "검색 결과"
    assert result["messages"][0].tool_call_id == "call_1"


@pytest.mark.asyncio
async def test_tool_executor_node_handles_tool_not_found():
    state = _make_state(
        tool_calls=[{"id": "call_1", "name": "unknown__tool", "args": {}}],
    )
    result = await tool_executor_node(
        state,
        lc_tool_map={},
        tool_spec_map={},
    )
    assert result["stop_reason"] is None
    assert "Tool not found" in result["messages"][0].content


@pytest.mark.asyncio
async def test_tool_executor_node_sets_stop_reason_on_stop_policy():
    tool = _make_tool(side_effect=RuntimeError("외부 API 장애"))
    spec = _make_spec(failure_policy=FailurePolicy.STOP)
    state = _make_state(
        tool_calls=[{"id": "call_1", "name": "catchup_kb__search", "args": {}}],
        allowed_tool_names=["catchup_kb.search"],
    )
    result = await tool_executor_node(
        state,
        lc_tool_map={"catchup_kb__search": tool},
        tool_spec_map={"catchup_kb.search": spec},
    )
    assert result["stop_reason"] is not None
    assert "catchup_kb.search" in result["stop_reason"]


@pytest.mark.asyncio
async def test_tool_executor_node_skip_adds_empty_tool_message():
    tool = _make_tool(side_effect=RuntimeError("optional tool failed"))
    spec = _make_spec(failure_policy=FailurePolicy.SKIP)
    state = _make_state(
        tool_calls=[{"id": "call_1", "name": "catchup_kb__search", "args": {}}],
        allowed_tool_names=["catchup_kb.search"],
    )
    result = await tool_executor_node(
        state,
        lc_tool_map={"catchup_kb__search": tool},
        tool_spec_map={"catchup_kb.search": spec},
    )
    assert result["stop_reason"] is None
    assert result["messages"][0].tool_call_id == "call_1"
    assert result["messages"][0].content == ""


# === tool_gate ===


def test_tool_gate_ends_when_no_tool_calls():
    state = _make_state(tool_calls=[], stop_reason=None)
    assert tool_gate(state) == END


def test_tool_gate_ends_on_stop_reason():
    state = _make_state(
        tool_calls=[{"id": "1", "name": "catchup_kb__search", "args": {}}],
        allowed_tool_names=["catchup_kb.search"],
        stop_reason="Tool failed with STOP policy",
    )
    assert tool_gate(state) == END


def test_tool_gate_routes_to_executor_when_allowed():
    state = _make_state(
        tool_calls=[{"id": "1", "name": "catchup_kb__search", "args": {}}],
        allowed_tool_names=["catchup_kb.search"],
        stop_reason=None,
    )
    assert tool_gate(state) == "tool_executor_node"


def test_tool_gate_routes_to_block_when_not_allowed():
    state = _make_state(
        tool_calls=[{"id": "1", "name": "unknown__tool", "args": {}}],
        allowed_tool_names=["catchup_kb.search"],
        stop_reason=None,
    )
    assert tool_gate(state) == "block_node"
