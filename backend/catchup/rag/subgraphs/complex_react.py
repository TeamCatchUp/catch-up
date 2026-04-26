from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.agents.complex_agent import complex_agent_node
from catchup.rag.agents.complex_agent import complex_planner_node
from catchup.rag.agents.complex_agent import gap_analysis_node
from catchup.rag.agents.standard_agent import collect_docs_node
from catchup.rag.agents.tools.search_tools import search_tool_executor_node
from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import merge_cache_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import rewrite_node
from catchup.rag.state import AgentState


def _route_after_complex_agent(state: AgentState) -> str:
    """tool_calls 있으면 executor, 없으면 gap_analysis로 라우팅.
    tool_calls 체크를 max_iterations보다 먼저 수행해 orphaned tool_use 메시지를 방지한다."""
    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if last and getattr(last, "tool_calls", None):
        return "tool_executor"

    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 7
    if state.get("agent_iteration", 0) >= max_iterations:
        return "collect_docs"

    return "gap_analysis"


def _route_after_gap_analysis(state: AgentState) -> str:
    """gap이 있고 반복 여유가 있으면 agent로, 그렇지 않으면 collect_docs로 라우팅."""
    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 7
    agent_iteration = state.get("agent_iteration", 0)

    gap_analysis = state.get("gap_analysis")
    if (
        gap_analysis is None
        or gap_analysis.is_sufficient
        or agent_iteration >= max_iterations
    ):
        return "collect_docs"
    return "complex_agent"


def build_complex_react_subgraph(
    llm_small, llm_large_stream, llm_thinking, vector_db_service, rerank_service
):
    """Complex ReAct 파이프라인 서브그래프.

    rewrite → planner (extended_thinking)
            → agent loop (LARGE, max_iter=7) ↔ tool executor
            → gap_analysis (extended_thinking)
            → [sufficient] collect_docs → rerank (1회) → generate_final_answer → END
            → [gaps remain] back to agent
    """
    graph = StateGraph(AgentState)

    graph.add_node("rewrite", partial(rewrite_node, llm=llm_small))
    graph.add_node("complex_planner", partial(complex_planner_node, llm=llm_thinking))
    graph.add_node("complex_agent", partial(complex_agent_node, llm=llm_thinking))
    graph.add_node(
        "tool_executor",
        partial(search_tool_executor_node, vector_db_service=vector_db_service),
    )
    graph.add_node("gap_analysis", partial(gap_analysis_node, llm=llm_thinking))
    graph.add_node("collect_docs", collect_docs_node)
    graph.add_node("rerank", partial(rerank_node, rerank_service=rerank_service))
    graph.add_node("merge_cache", merge_cache_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
    )

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "complex_planner")
    graph.add_edge("complex_planner", "complex_agent")
    graph.add_conditional_edges(
        "complex_agent",
        _route_after_complex_agent,
        {
            "tool_executor": "tool_executor",
            "gap_analysis": "gap_analysis",
            "collect_docs": "collect_docs",
        },
    )
    graph.add_edge("tool_executor", "complex_agent")
    graph.add_conditional_edges(
        "gap_analysis",
        _route_after_gap_analysis,
        {
            "complex_agent": "complex_agent",
            "collect_docs": "collect_docs",
        },
    )
    graph.add_edge("collect_docs", "rerank")
    graph.add_edge("rerank", "merge_cache")
    graph.add_edge("merge_cache", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
