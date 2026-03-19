import logging
from functools import partial
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END
from langgraph.graph import StateGraph

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.llm.factory import LlmProvider
from catchup.components.llm.factory import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.components.reranker.constants import RerankerProvider
from catchup.components.reranker.factory import get_rerank_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.rag.conditional_edges import route_after_grade
from catchup.rag.conditional_edges import route_question
from catchup.rag.nodes import chitchat_node
from catchup.rag.nodes import generate_final_answer_node
from catchup.rag.nodes import generate_vector_queries_node
from catchup.rag.nodes import grade_node
from catchup.rag.nodes import rerank_node
from catchup.rag.nodes import rewrite_node
from catchup.rag.nodes import route_node
from catchup.rag.nodes import search_vector_db_node
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


def get_compiled_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None
):
    
    # 분석용 (small)
    analysis_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False
    ).get_llm()
    
    # 일상 대화용 (small)
    chitchat_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=True
    ).get_llm()
    
    # 최종 답변 생성용 llm (large)
    final_llm = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.LARGE,
        streaming=True
    ).get_llm()
    
    # Vector DB 서비스
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_db_service = get_vector_db_service(VectorDbProvider.PGVECTOR, embeddings)
    
    # Reranker 서비스
    # Bedrock Rerank는 async API를 제공하지 않으므로,
    # Service 레벨에서 sync 호출을 executor로 감싸
    # 상위 Node/Graph에서는 항상 await 가능한 인터페이스만 사용하도록 한다.
    rerank_service = get_rerank_service(RerankerProvider.AWS_BEDROCK)

    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node(
        node="route", 
        action=partial(route_node, llm=analysis_llm)
    )
    workflow.add_node(
        node="rewrite", 
        action=partial(rewrite_node, llm=analysis_llm)
    )
    workflow.add_node(
        node="generate_vector_queries",
        action=partial(generate_vector_queries_node, llm=analysis_llm)
    )
    workflow.add_node(
        node="search_vector_db", 
        action=partial(search_vector_db_node, vector_db_service=vector_db_service)
    )
    workflow.add_node(
        node="rerank", 
        action=partial(rerank_node, rerank_service=rerank_service)
    )
    workflow.add_node(
        node="grade",
        action=partial(grade_node, llm=analysis_llm)
    )
    workflow.add_node(
        node="chitchat", 
        action=partial(chitchat_node, llm=chitchat_llm)
    )
    workflow.add_node(
        node="generate_final_answer", 
        action=partial(generate_final_answer_node, llm=final_llm)
    )
    # workflow.add_node("expand_graph_context", expand_graph_context_node)
    # workflow.add_node("fetch_details_after_graph_context_expansion", fetch_details_after_graph_context_expansion_node)
    # workflow.add_node("fallback_cypher_query", fallback_cypher_query_node)

    # Edges
    workflow.set_entry_point("route")
    workflow.add_conditional_edges(
        "route",
        route_question,
        {
            "rewrite": "rewrite",
            "chitchat": "chitchat"
        }
    )
    workflow.add_edge("chitchat", END)
    workflow.add_edge("rewrite", "generate_vector_queries")
    workflow.add_edge("generate_vector_queries", "search_vector_db")
    workflow.add_edge("search_vector_db", "rerank")
    workflow.add_edge("rerank", "grade")
    workflow.add_conditional_edges(
        "grade",
        route_after_grade,
        {
            "generate_final_answer": "generate_final_answer",
            "rewrite": "rewrite",
            # "expand_graph_context": "expand_graph_context",
            # "fallback_cypher_query": "fallback_cypher_query"
        }
    )
    # workflow.add_edge("expand_graph_context", "fetch_details_after_graph_context_expansion")
    # workflow.add_edge("fetch_details_after_graph_context_expansion", "generate_final_answer")
    # workflow.add_edge("fallback_cypher_query", "generate_final_answer")
    workflow.add_edge("generate_final_answer", END)

    # Thread(session)-level 단기 영속성
    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)
    
    return workflow.compile()