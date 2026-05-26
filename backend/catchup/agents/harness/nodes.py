from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END

from catchup.agents.harness.state import ExecutionState


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
) -> dict:
    """tool_gate를 통과한 모든 tool_call을 실행하고 ToolMessage 리스트를 반환한다."""
    tool_messages: list[ToolMessage] = []

    for tool_call in state["messages"][-1].tool_calls:
        tool = lc_tool_map.get(tool_call["name"])
        try:
            if tool is None:
                raise KeyError(f"Tool not found: {tool_call['name']}")
            result = await tool.ainvoke(tool_call["args"])
            content = str(result)
        except Exception as e:
            content = f"Tool execution failed: {e}"

        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

    return {"messages": tool_messages}


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

    tool_call 없음 → END
    모든 tool_call이 allowlist 통과 → tool_executor_node
    하나라도 allowlist 실패 → block_node
    """
    last_message = state["messages"][-1]

    if not getattr(last_message, "tool_calls", None):
        return END

    for tool_call in last_message.tool_calls:
        spec_name = tool_call["name"].replace("__", ".", 1)
        if spec_name not in state["allowed_tool_names"]:
            return "block_node"

    return "tool_executor_node"
