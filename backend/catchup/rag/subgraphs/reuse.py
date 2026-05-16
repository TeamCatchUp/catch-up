from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import prepare_cache_node
from catchup.rag.state import AgentState


def build_reuse_subgraph(llm_large_stream):
    """Reuse 파이프라인 서브그래프.

    직전 검색 턴의 doc_cache를 그대로 answer node에 전달한다. 재검색 없음, rerank 없음.

    rewrite 없음: supervisor가 rewritten_query = original_query를 미리 설정한다.
    generate_final_answer_node의 LARGE LLM이 conversation_history로 coreference를 해소한다.
    """
    from catchup.rag.graph import BASE_RETRY_POLICY

    graph = StateGraph(AgentState)

    graph.add_node("prepare_cache", prepare_cache_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large_stream),
        metadata={"tags": ["stream_target", "has_citations"]},
        retry=BASE_RETRY_POLICY,
    )

    graph.set_entry_point("prepare_cache")
    graph.add_edge("prepare_cache", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
