from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import prepare_cache_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import rewrite_node
from catchup.rag.state import AgentState


def build_reuse_subgraph(llm_small, llm_large_stream, rerank_service):
    """Reuse 파이프라인 서브그래프.

    새 검색 없이 doc_cache를 현재 쿼리 기준으로 재정렬 후 답변을 생성한다.
    prepare_cache: doc_cache → retrieved_docs 복사
    rerank: rewritten_query 기준 재정렬 → RERANK_TOTAL_K로 bound
    """
    
    from catchup.rag.graph import TIMEOUT_RETRY_POLICY

    graph = StateGraph(AgentState)

    graph.add_node(
        "rewrite",
        partial(rewrite_node, llm=llm_small, timeout=10.0),
        retry=TIMEOUT_RETRY_POLICY,
    )
    graph.add_node("prepare_cache", prepare_cache_node)
    graph.add_node("rerank", partial(rerank_node, rerank_service=rerank_service))
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
    )

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "prepare_cache")
    graph.add_edge("prepare_cache", "rerank")
    graph.add_edge("rerank", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
