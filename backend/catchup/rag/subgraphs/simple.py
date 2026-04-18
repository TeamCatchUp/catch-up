from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.nodes import generate_final_answer_fast_node
from catchup.rag.nodes import generate_vector_queries_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import search_vector_db_node
from catchup.rag.state import AgentState


async def _record_search_turn_node(state: AgentState):
    """검색 완료 시점의 턴 번호를 last_search_turn에 기록한다."""
    return {"last_search_turn": state.get("turn_number", 0)}


def build_simple_subgraph(llm_small, llm_fast, vector_db_service, rerank_service):
    """Simple 파이프라인 서브그래프.

    단일 쿼리 검색 → rerank → fast generation.
    pipeline_plan.pipeline_type == "simple"이면 generate_vector_queries_node가
    자동으로 쿼리 수를 1개로 제한한다.
    supervisor가 rewritten_query = original_query로 미리 채워두므로 rewrite 불필요.
    """
    graph = StateGraph(AgentState)

    graph.add_node(
        "generate_vector_queries",
        partial(generate_vector_queries_node, llm=llm_small),
    )
    graph.add_node(
        "search_vector_db",
        partial(search_vector_db_node, vector_db_service=vector_db_service),
    )
    graph.add_node("rerank", partial(rerank_node, rerank_service=rerank_service))
    graph.add_node("record_search_turn", _record_search_turn_node)
    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_fast_node, llm=llm_fast),
    )

    graph.set_entry_point("generate_vector_queries")
    graph.add_edge("generate_vector_queries", "search_vector_db")
    graph.add_edge("search_vector_db", "rerank")
    graph.add_edge("rerank", "record_search_turn")
    graph.add_edge("record_search_turn", "generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
