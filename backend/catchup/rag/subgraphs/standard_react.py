from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.agents.standard_agent import collect_docs_node
from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.rag.agents.tools.search_tools import search_tool_executor_node
from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import merge_cache_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import rewrite_node
from catchup.rag.state import AgentState


def _route_after_agent(state: AgentState) -> str:
    """tool_calls 있으면 executor, 없으면 collect_docs로 라우팅.
    tool_calls 체크를 max_iterations보다 먼저 수행해 orphaned tool_use 메시지를 방지한다."""
    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if last and getattr(last, "tool_calls", None):
        return "tool_executor"

    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 3
    if state.get("agent_iteration", 0) >= max_iterations:
        return "collect_docs"

    return "collect_docs"


def build_standard_react_subgraph(
    llm_small, llm_large_stream, llm_thinking, vector_db_service, rerank_service
):
    """Standard ReAct 파이프라인 서브그래프.

    rewrite → agent loop (SMALL, max_iter=3) ↔ tool executor
            → collect_docs → rerank (1회) → generate_final_answer → END
    """
    from catchup.rag.graph import AGENT_TIMEOUT_RETRY_POLICY
    from catchup.rag.graph import TIMEOUT_RETRY_POLICY

    graph = StateGraph(AgentState)

    graph.add_node(
        "rewrite",
        partial(rewrite_node, llm=llm_small, timeout=10.0),
        retry=AGENT_TIMEOUT_RETRY_POLICY,
    )
    graph.add_node(
        "standard_agent",
        partial(standard_agent_node, llm=llm_thinking),
        retry=AGENT_TIMEOUT_RETRY_POLICY,
    )
    graph.add_node(
        "tool_executor",
        partial(search_tool_executor_node, vector_db_service=vector_db_service),
    )
    graph.add_node("collect_docs", collect_docs_node)
    graph.add_node(
        "rerank",
        partial(rerank_node, rerank_service=rerank_service),
        retry=TIMEOUT_RETRY_POLICY,
    )
    graph.add_node("merge_cache", merge_cache_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
        retry=TIMEOUT_RETRY_POLICY,
    )

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "standard_agent")
    graph.add_conditional_edges(
        "standard_agent",
        _route_after_agent,
        {
            "tool_executor": "tool_executor",
            "collect_docs": "collect_docs",
        },
    )
    graph.add_edge("tool_executor", "standard_agent")
    graph.add_edge("collect_docs", "rerank")
    graph.add_edge("rerank", "merge_cache")
    graph.add_edge("merge_cache", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
