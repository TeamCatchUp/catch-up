from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from catchup.agents.harness.prompt_renderer import render_system_prompt
from catchup.agents.harness.state import ExecutionState
from catchup.agents.schemas import AgentSpec
from catchup.agents.tools.registry import ToolRegistry


async def _agent_node(state: ExecutionState, llm_with_tools: BaseChatModel) -> dict:
    """LLM이 다음 tool_call 또는 최종 응답을 결정한다."""
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}


async def _tool_executor(state: ExecutionState) -> dict:
    """tool_gate를 통과한 tool_call을 실행한다."""
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]

    lc_tools = ToolRegistry.get_langchain_tools([tool_call["name"]])
    tool = lc_tools[0]

    try:
        result = await tool.ainvoke(tool_call["args"])
        content = str(result)
    except Exception as e:
        content = f"Tool execution failed: {e}"

    return {
        "messages": [
            ToolMessage(content=content, tool_call_id=tool_call["id"])
        ]
    }


def _tool_gate(state: ExecutionState) -> str:
    """마지막 메시지에 tool_call이 있으면 allowlist 검증 후 라우팅한다.

    tool_call이 없으면 → END (LLM이 완료 판단)
    allowlist 통과 → tool_executor
    allowlist 실패 → block (ToolMessage error 주입 후 agent_node로 복귀)
    """
    last_message = state["messages"][-1]

    if not getattr(last_message, "tool_calls", None):
        return END

    tool_call = last_message.tool_calls[0]
    if tool_call["name"] not in state["allowed_tool_names"]:
        return "block"

    return "execute"


async def _block_node(state: ExecutionState) -> dict:
    """allowlist를 벗어난 tool_call을 차단하고 에러를 LLM에 돌려준다."""
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0]
    return {
        "messages": [
            ToolMessage(
                content=f"Tool not allowed: {tool_call['name']}",
                tool_call_id=tool_call["id"],
            )
        ]
    }


def build_execution_graph(spec: AgentSpec, llm: BaseChatModel) -> CompiledStateGraph:
    """AgentSpec 기준으로 Execution Agent LangGraph를 빌드한다.

    prebuilt create_react_agent를 쓰지 않는 이유:
    tools_node가 블랙박스라 tool_gate 삽입이 불가능하다.
    """
    allowed_tool_names = [t.name for t in spec.tools]
    lc_tools = ToolRegistry.get_langchain_tools(allowed_tool_names)
    llm_with_tools = llm.bind_tools(lc_tools)

    async def agent_node(state: ExecutionState) -> dict:
        return await _agent_node(state, llm_with_tools)

    graph = StateGraph(ExecutionState)
    graph.add_node("agent_node", agent_node)
    graph.add_node("tool_executor", _tool_executor)
    graph.add_node("block", _block_node)

    graph.set_entry_point("agent_node")

    graph.add_conditional_edges(
        "agent_node",
        _tool_gate,
        {"execute": "tool_executor", "block": "block", END: END},
    )
    graph.add_edge("tool_executor", "agent_node")
    graph.add_edge("block", "agent_node")

    return graph.compile()


async def run_execution_agent(
    spec: AgentSpec,
    user_input_values: dict,
    trigger_payload: dict,
    graph: CompiledStateGraph,
    invoke_config: dict,
) -> str:
    """Execution Agent를 실행하고 최종 응답 텍스트를 반환한다.

    graph와 invoke_config는 ExecutionService에서 주입받는다.
    graph 캐싱과 Langfuse 설정은 호출자(ExecutionService) 책임이다.
    """
    system_prompt = render_system_prompt(spec, user_input_values, trigger_payload)
    allowed_tool_names = [t.name for t in spec.tools]

    initial_state: ExecutionState = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Execute your task based on the trigger context provided in the system prompt."),
        ],
        "allowed_tool_names": allowed_tool_names,
    }

    final_state = await graph.ainvoke(initial_state, invoke_config)
    return final_state["messages"][-1].content
