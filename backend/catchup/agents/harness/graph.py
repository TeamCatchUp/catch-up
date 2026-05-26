from functools import partial

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from catchup.agents.harness.nodes import agent_node
from catchup.agents.harness.nodes import block_node
from catchup.agents.harness.nodes import tool_executor_node
from catchup.agents.harness.nodes import tool_gate
from catchup.agents.harness.prompt_renderer import render_system_prompt
from catchup.agents.harness.state import ExecutionState
from catchup.agents.schemas import AgentSpec
from catchup.agents.tools.registry import ToolRegistry


def _build_lc_tool_map(
    allowed_tool_names: list[str],
) -> dict[str, StructuredTool]:
    """allowed_tool_names에 해당하는 LangChain 툴 맵을 반환한다."""
    lc_tool_map: dict[str, StructuredTool] = {}
    for lc_tool in ToolRegistry.get_langchain_tools(allowed_tool_names):
        lc_tool_map[lc_tool.name] = lc_tool
    return lc_tool_map


def build_execution_graph(
    spec: AgentSpec,
    llm: BaseChatModel,
) -> CompiledStateGraph:
    """AgentSpec 기준으로 Execution Agent LangGraph를 빌드하고 컴파일한다.

    prebuilt create_react_agent를 쓰지 않는 이유:
    tools_node가 블랙박스라 tool_gate 삽입이 불가능하다.
    """
    allowed_tool_names = [t.name for t in spec.tools]
    lc_tool_map = _build_lc_tool_map(allowed_tool_names)
    lc_tools = list(lc_tool_map.values())
    llm_with_tools = llm.bind_tools(lc_tools)

    graph = StateGraph(ExecutionState)
    graph.add_node("agent_node", partial(agent_node, llm_with_tools=llm_with_tools))
    graph.add_node("tool_executor_node", partial(tool_executor_node, lc_tool_map=lc_tool_map))
    graph.add_node("block_node", block_node)

    graph.set_entry_point("agent_node")
    graph.add_conditional_edges(
        "agent_node",
        tool_gate,
        {
            "tool_executor_node": "tool_executor_node",
            "block_node": "block_node",
            END: END
        },
    )
    graph.add_edge("tool_executor_node", "agent_node")
    graph.add_edge("block_node", "agent_node")

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
