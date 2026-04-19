from functools import partial

from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.state import AgentState


def build_reuse_subgraph(llm_large):
    """Reuse 파이프라인 서브그래프.

    이전 턴에서 검색된 retrieved_docs를 재사용해 새 검색 없이 즉시 답변을 생성한다.
    supervisor가 rewritten_query = original_query로 미리 채워두므로 rewrite 불필요.
    """
    graph = StateGraph(AgentState)

    graph.add_node(
        "generate_final_answer",
        partial(generate_final_answer_node, llm=llm_large),
    )

    graph.set_entry_point("generate_final_answer")
    graph.add_edge("generate_final_answer", END)

    return graph.compile()
