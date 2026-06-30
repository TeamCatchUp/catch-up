from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.langgraph.retry import AGENT_RETRY_POLICY
from catchup.langgraph.retry import BASE_RETRY_POLICY
from catchup.rag.agents.limit_extraction import extract_essential_node
from catchup.rag.agents.standard_agent import collect_docs_node
from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.rag.agents.tools.search_tools import search_tool_executor_node
from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import merge_cache_node
from catchup.rag.nodes import prepare_cache_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import rewrite_node
from catchup.rag.nodes import select_final_docs_node
from catchup.rag.state import AgentState


def _route_after_agent(state: AgentState) -> str:
    """agent_stop_reason == 'by_choice' (submit_result 또는 no-tool-call) → collect_docs.
    tool_calls 체크를 max_iterations보다 먼저 수행해 orphaned tool_use 메시지를 방지한다."""
    stop_reason = state.get("agent_stop_reason")
    if stop_reason == "by_choice":
        return "collect_docs"
    if stop_reason == "iteration_limit":
        return "extract_essential"

    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if last and getattr(last, "tool_calls", None):
        return "tool_executor"

    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 4
    if state.get("agent_iteration", 0) >= max_iterations:
        return "extract_essential"

    return "collect_docs"


def build_standard_react_subgraph(
    llm_small, llm_large_stream, llm_large_stream_thinking, vector_db_service, rerank_service
):
    """Standard ReAct 파이프라인 서브그래프.

    rewrite → agent loop (SMALL, max_iter=3) ↔ tool executor
            → collect_docs → rerank (1회) → generate_final_answer → END
    """
    graph = StateGraph(AgentState)

    graph.add_node(
        "rewrite",
        partial(rewrite_node, llm=llm_small, timeout=10.0),
        retry=AGENT_RETRY_POLICY,
    )
    graph.add_node(
        "prepare_cache",
        partial(prepare_cache_node, vector_db_service=vector_db_service),
    )
    graph.add_node(
        "standard_agent",
        partial(standard_agent_node, llm=llm_small),
        retry=AGENT_RETRY_POLICY,
    )
    graph.add_node(
        "tool_executor",
        partial(search_tool_executor_node, vector_db_service=vector_db_service),
    )
    graph.add_node(
        "extract_essential",
        partial(extract_essential_node, llm=llm_small),
        retry=BASE_RETRY_POLICY,
    )
    graph.add_node("collect_docs", collect_docs_node)
    graph.add_node(
        "rerank",
        partial(rerank_node, rerank_service=rerank_service),
        retry=BASE_RETRY_POLICY,
    )
    graph.add_node(
        "select_final_docs",
        select_final_docs_node,
    )
    graph.add_node("merge_cache", merge_cache_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large_stream_thinking, llm_fast=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
        retry=BASE_RETRY_POLICY,
    )

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "prepare_cache")
    graph.add_edge("prepare_cache", "standard_agent")
    graph.add_conditional_edges(
        "standard_agent",
        _route_after_agent,
        {
            "tool_executor": "tool_executor",
            "extract_essential": "extract_essential",
            "collect_docs": "collect_docs",
        },
    )
    graph.add_edge("tool_executor", "standard_agent")
    graph.add_edge("extract_essential", "collect_docs")
    graph.add_edge("collect_docs", "rerank")
    graph.add_edge("rerank", "select_final_docs")
    graph.add_edge("select_final_docs", "merge_cache")
    graph.add_edge("merge_cache", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
