from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.graph import END, StateGraph
from redis.asyncio import Redis

from app.core.config import settings
from app.observability.langfuse_client import langfuse_handler
from app.rag.node import (
    chitchat_node,
    generate_node,
    grade_node,
    retrieve_node,
    rewrite_node,
    router_node,
)
from app.rag.state import AgentState


def route_question(state: AgentState):
    datasource = state.get("datasource")
    if datasource == "chitchat":
        return "chitchat"
    return "rewrite"


def route_after_grade(state: AgentState):
    grade_status = state.get("grade_status")
    if grade_status == "bad":
        return "rewrite"
    return "generate"
    


async def get_compiled_graph():
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("router", router_node)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("rewrite", rewrite_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("generate", generate_node)

    workflow.set_entry_point("router")
    
    workflow.add_conditional_edges(
        "router",
        route_question,
        {
            "rewrite": "rewrite",
            "chitchat": "chitchat"
        }
    )
    workflow.add_edge("chitchat", END)
    
    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("retrieve", "grade")
    workflow.add_conditional_edges(
        "grade",
        route_after_grade,
        {
            "generate": "generate", 
            "rewrite": "rewrite"
        },
    )

    workflow.add_edge("generate", END)

    redis_client = Redis.from_url(settings.REDIS_URL)
    checkpointer = AsyncRedisSaver(redis_client=redis_client)

    await checkpointer.setup()  # 인덱스 생성

    return workflow.compile(checkpointer=checkpointer).with_config(
        {"callbacks": [langfuse_handler]}
    )
