import asyncio

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END

from catchup.agents.enums import FailurePolicy
from catchup.agents.harness.state import ExecutionState
from catchup.agents.schemas import ToolSpec

logger = structlog.get_logger()

_BACKOFF_BASE = 2
_RETRYABLE = (asyncio.TimeoutError, ConnectionError, OSError)


async def _execute_with_policy(
    tool: StructuredTool,
    args: dict,
    spec: ToolSpec,
) -> tuple[str, bool]:
    """tool을 실행하고 (content, should_stop) 쌍을 반환한다.

    성공 시: (결과 문자열, False)
    실패 시: failure_policy에 따라
      SKIP     → ("", False)          LLM에 숨김, 루프 계속
      CONTINUE → (에러 메시지, False)  LLM에 전달, 루프 계속
      STOP     → (에러 메시지, True)   LLM에 전달, 루프 종료
    재시도는 RETRYABLE 예외에 한해 max_retry 횟수만큼 지수 백오프로 수행한다.
    """
    max_attempts = 1 + (spec.max_retry or 0)
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            result = await tool.ainvoke(args)
            # TODO: output_model 직렬화 활성화 시 대체 필요
            content = result if isinstance(result, str) else str(result)
            return content, False
        except _RETRYABLE as e:
            last_error = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(_BACKOFF_BASE ** attempt)
        except Exception as e:
            last_error = e
            break  # non-retryable → 즉시 정책 분기

    match spec.failure_policy:
        case FailurePolicy.SKIP:
            return "", False
        case FailurePolicy.CONTINUE:
            logger.error("tool_failure", tool=spec.name, error=str(last_error))
            return f"Tool execution failed: {last_error}", False
        case FailurePolicy.STOP:
            logger.error("tool_failure_stop", tool=spec.name, error=str(last_error))
            return f"Tool execution failed: {last_error}", True
        case _:
            return f"Tool execution failed: {last_error}", False


async def agent_node(
    state: ExecutionState,
    *,
    llm_with_tools: BaseChatModel,
) -> dict:
    """LLM이 다음 tool_call 또는 최종 응답을 결정한다."""
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}


async def tool_executor_node(
    state: ExecutionState,
    *,
    lc_tool_map: dict[str, StructuredTool],
    tool_spec_map: dict[str, ToolSpec],
) -> dict:
    """tool_gate를 통과한 모든 tool_call을 실행하고 ToolMessage 리스트를 반환한다."""
    tool_messages: list[ToolMessage] = []
    stop_reason: str | None = None

    for tool_call in state["messages"][-1].tool_calls:
        name = tool_call["name"]
        tool = lc_tool_map.get(name)

        if tool is None:
            tool_messages.append(
                ToolMessage(
                    content=f"Tool not found: {name}",
                    tool_call_id=tool_call["id"],
                )
            )
            continue

        spec_name = name.replace("__", ".", 1)
        spec = tool_spec_map[spec_name]
        content, should_stop = await _execute_with_policy(tool, tool_call["args"], spec)

        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

        if should_stop:
            stop_reason = f"Tool '{spec_name}' failed with STOP policy"
            break

    return {"messages": tool_messages, "stop_reason": stop_reason}


async def block_node(state: ExecutionState) -> dict:
    """allowlist를 벗어난 tool_call을 차단하고 에러를 LLM에 돌려준다."""
    return {
        "messages": [
            ToolMessage(
                content=f"Tool not allowed: {tool_call['name']}",
                tool_call_id=tool_call["id"],
            )
            for tool_call in state["messages"][-1].tool_calls
        ]
    }


def tool_gate(state: ExecutionState) -> str:
    """마지막 메시지에 tool_call이 있으면 allowlist 검증 후 라우팅한다.

    stop_reason 있음 → END  (STOP 정책 발동 후 LLM이 재시도해도 강제 종료)
    tool_call 없음 → END
    모든 tool_call이 allowlist 통과 → tool_executor_node
    하나라도 allowlist 실패 → block_node
    """
    if state.get("stop_reason"):
        return END

    last_message = state["messages"][-1]

    if not getattr(last_message, "tool_calls", None):
        return END

    for tool_call in last_message.tool_calls:
        spec_name = tool_call["name"].replace("__", ".", 1)
        if spec_name not in state["allowed_tool_names"]:
            return "block_node"

    return "tool_executor_node"
