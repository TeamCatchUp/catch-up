from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import prepare_cache_node
from catchup.rag.state import AgentState


def build_reuse_subgraph(llm_large_stream, vector_db_service: BaseVectorDbService):
    """Reuse 파이프라인 서브그래프.

    doc_cache(hot cache)를 기본으로 하고, supervisor가 reuse_history_turn_numbers를
    지정한 경우 해당 검색 턴의 docs를 DB에서 lazy fetch하여 병합한다.

    rewrite 없음: supervisor가 rewritten_query = original_query를 미리 설정한다.
    generate_final_answer_node의 LARGE LLM이 conversation_history로 coreference를 해소한다.
    """
    from catchup.rag.graph import BASE_RETRY_POLICY

    graph = StateGraph(AgentState)

    graph.add_node(
        "prepare_cache",
        partial(prepare_cache_node, vector_db_service=vector_db_service),
    )
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
