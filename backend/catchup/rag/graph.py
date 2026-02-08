import logging
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.graph import END, StateGraph
from redis.asyncio import Redis

from catchup.configs.config import settings
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


async def get_compiled_graph():
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("route", route_node)
    # workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("rewrite", rewrite_node)
    workflow.add_node("generate_vector_queries", generate_vector_queries_node)
    workflow.add_node("search_vector_db", search_vector_db_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("expand_graph_context", expand_graph_context_node)
    workflow.add_node("fetch_details_after_graph_context_expansion", fetch_details_after_graph_context_expansion_node)
    workflow.add_node("fallback_cypher_query", fallback_cypher_query_node)
    workflow.add_node("generate_final_answer", generate_final_answer_node)

    workflow.set_entry_point("route")

    # workflow.add_conditional_edges(
    #     "router",
    #     route_question, 
    #     {
    #         "rewrite": "rewrite",
    #         "chitchat": "chitchat"
    #     }
    # )
    # workflow.add_edge("chitchat", END)

    workflow.add_edge("route", "rewrite")
    workflow.add_edge("rewrite", "generate_vector_queries")
    workflow.add_edge("generate_vector_queries", "search_vector_db")
    workflow.add_edge("search_vector_db", "rerank")
    workflow.add_edge("rerank", "grade")
    workflow.add_conditional_edges(
        "grade",
        route_after_grade,
        {
            "generate": "generate_final_answer",
            "rewrite": "rewrite",
            "expand_graph_context": "expand_graph_context",
            "fallback_cypher_query": "fallback_cypher_query"
        }
    )
    workflow.add_edge("expand_graph_context", "fetch_details_after_graph_context_expansion")
    workflow.add_edge("fetch_details_after_graph_context_expansion", "generate_final_answer")
    workflow.add_edge("fallback_cypher_query", "generate_final_answer")
    workflow.add_edge("generate_final_answer", END)

    redis_client = Redis.from_url(settings.REDIS_URL)

    # Thread(session)-level 단기 영속성
    checkpointer = AsyncRedisSaver(redis_client=redis_client)

    await checkpointer.setup()  # 인덱스 생성

    return workflow.compile(checkpointer=checkpointer)
