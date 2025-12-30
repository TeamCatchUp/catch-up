from app.core.config import settings
from app.rag.node import generate_node, grade_node, retrieve_node, rewrite_node
from app.rag.state import AgentState
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.graph import END, StateGraph
from redis.asyncio import Redis


async def get_compiled_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("rewrite", rewrite_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)

    workflow.set_entry_point("rewrite")

    workflow.add_edge("rewrite", "retrieve")

    workflow.add_conditional_edges(
        "retrieve",
        grade_node,
        {"generate_answer": "generate", "rewrite_answer": "rewrite"},
    )

    workflow.add_edge("generate", END)

    redis_client = Redis.from_url(settings.REDIS_URL)
    checkpointer = AsyncRedisSaver(redis_client=redis_client)

    await checkpointer.setup()  # 인덱스 생성

    return workflow.compile(checkpointer=checkpointer)
