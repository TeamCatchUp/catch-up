from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.agents.complex_agent import complex_agent_node
from catchup.rag.agents.complex_agent import complex_planner_node
from catchup.rag.agents.limit_extraction import extract_essential_node
from catchup.rag.agents.standard_agent import collect_docs_node
from catchup.rag.agents.tools.search_tools import search_tool_executor_node
from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import merge_cache_node
from catchup.rag.nodes import prepare_cache_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import rewrite_node
from catchup.rag.state import AgentState


def _route_after_prepare_cache(state: AgentState) -> str:
    """retrieved_docs가 비어있으면 (cold cache) planner로 직행.
    캐시가 있을 때만 agent iter-0 cache 평가 단계를 거친다."""
    if not state.get("retrieved_docs"):
        return "complex_planner"
    return "complex_agent"


def _route_after_complex_agent(state: AgentState) -> str:
    """agent_stop_reason == 'by_choice' (submit_result) → collect_docs.
    tool_calls 체크를 max_iterations보다 먼저 수행해 orphaned tool_use 메시지를 방지한다.

    search_plan이 없는 상태에서 search tool_calls가 있으면 complex_planner로 먼저 라우팅한다.
    iter-0의 tool_calls는 "검색 필요" 신호로만 사용되며, drop_orphaned_tool_calls가 정리한다.
    """
    if state.get("agent_stop_reason") == "by_choice":
        return "collect_docs"

    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if last and getattr(last, "tool_calls", None):
        if state.get("search_plan") is None:
            return "complex_planner"
        return "tool_executor"

    pipeline_plan = state.get("pipeline_plan")
    max_iterations = pipeline_plan.max_iterations if pipeline_plan else 8
    if state.get("agent_iteration", 0) >= max_iterations:
        return "extract_essential"

    return "collect_docs"


def build_complex_react_subgraph(
    llm_small, llm_large_stream, llm_thinking, vector_db_service, rerank_service
):
    """Complex ReAct 파이프라인 서브그래프.

    rewrite → prepare_cache
      → cold cache (retrieved_docs 없음) → complex_planner → agent iter-0+
      → warm cache (retrieved_docs 있음) → agent iter-0 (cache 평가)
          → cache 충분 (no tool calls)        → collect_docs → rerank → generate
          → cache 부족 (tool calls, no plan)  → complex_planner → agent iter-1+
                ↔ tool executor (max_iter=8)
                → collect_docs → rerank (1회) → generate_final_answer → END
    """
    from catchup.rag.graph import AGENT_RETRY_POLICY
    from catchup.rag.graph import BASE_RETRY_POLICY

    graph = StateGraph(AgentState)

    graph.add_node(
        "rewrite",
        partial(rewrite_node, llm=llm_small, timeout=10.0),
        retry=BASE_RETRY_POLICY,
    )
    graph.add_node(
        "prepare_cache",
        partial(prepare_cache_node, vector_db_service=vector_db_service),
    )
    graph.add_node(
        "complex_planner",
        partial(complex_planner_node, llm=llm_thinking),
        retry=BASE_RETRY_POLICY,
    )
    graph.add_node(
        "complex_agent",
        partial(complex_agent_node, llm=llm_thinking),
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
    graph.add_node("merge_cache", merge_cache_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
        retry=BASE_RETRY_POLICY,
    )

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "prepare_cache")
    graph.add_conditional_edges(
        "prepare_cache",
        _route_after_prepare_cache,
        {"complex_planner": "complex_planner", "complex_agent": "complex_agent"},
    )
    graph.add_edge("complex_planner", "complex_agent")
    graph.add_conditional_edges(
        "complex_agent",
        _route_after_complex_agent,
        {
            "complex_planner": "complex_planner",
            "tool_executor": "tool_executor",
            "extract_essential": "extract_essential",
            "collect_docs": "collect_docs",
        },
    )
    graph.add_edge("tool_executor", "complex_agent")
    graph.add_edge("extract_essential", "collect_docs")
    graph.add_edge("collect_docs", "rerank")
    graph.add_edge("rerank", "merge_cache")
    graph.add_edge("merge_cache", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
