from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.nodes import generate_final_answer_fast_node
from catchup.rag.nodes import generate_vector_queries_node
from catchup.rag.nodes import merge_cache_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import search_vector_db_node
from catchup.rag.state import AgentState


def build_simple_subgraph(
    llm_small, llm_large_stream, vector_db_service, rerank_service
):
    """Simple 파이프라인 서브그래프.

    단일 쿼리 검색 → rerank → fast generation.
    pipeline_plan.pipeline_type == "simple"이면 generate_vector_queries_node가
    자동으로 쿼리 수를 1개로 제한한다.
    supervisor가 rewritten_query = original_query로 미리 채워두므로 rewrite 불필요.
    """
    from catchup.rag.graph import TIMEOUT_RETRY_POLICY

    graph = StateGraph(AgentState)

    graph.add_node(
        "generate_vector_queries",
        partial(generate_vector_queries_node, llm=llm_small, timeout=15.0),
        retry=TIMEOUT_RETRY_POLICY,
    )
    graph.add_node(
        "search_vector_db",
        partial(search_vector_db_node, vector_db_service=vector_db_service),
    )
    graph.add_node("rerank", partial(rerank_node, rerank_service=rerank_service))
    graph.add_node("merge_cache", merge_cache_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_fast_node, llm=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
    )

    graph.set_entry_point("generate_vector_queries")
    graph.add_edge("generate_vector_queries", "search_vector_db")
    graph.add_edge("search_vector_db", "rerank")
    graph.add_edge("rerank", "merge_cache")
    graph.add_edge("merge_cache", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
