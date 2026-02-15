from functools import partial
import logging
from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from catchup.components.llm.factory import LlmProvider, ModelCapacity, get_llm_service
from catchup.rag.conditional_edges import route_after_grade, route_question
from catchup.rag.nodes import (
    chitchat_node,
    generate_final_answer_node,
    grade_node,
    generate_vector_queries_node,
    rerank_node,
    search_vector_db_node,
    expand_graph_context_node,
    fetch_details_after_graph_context_expansion_node,
    rewrite_node,
    route_node,
    fallback_cypher_query_node,
)
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


def get_compiled_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None
):
    
    # 분석 및 일상 대화용 (small)
    analysis_llm = get_llm_service(LlmProvider.AWS_BEDROCK, ModelCapacity.SMALL).get_llm()
    
    # 최종 답변 생성용 llm (large)
    final_llm = get_llm_service(LlmProvider.AWS_BEDROCK, ModelCapacity.LARGE).get_llm()    

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
        action=search_vector_db_node
    )
    workflow.add_node(
        node="rerank", 
        action=rerank_node
    )
    workflow.add_node(
        node="grade",
        action=partial(grade_node, llm=analysis_llm)
    )
    workflow.add_node(
        node="chitchat", 
        action=partial(chitchat_node, llm=analysis_llm)
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