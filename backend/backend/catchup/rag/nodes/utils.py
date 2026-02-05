# llm 호출 Rate Limit 방어
import asyncio
from typing import Annotated

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

llm_semaphore = asyncio.Semaphore(10)
rerank_semaphore = asyncio.Semaphore(10)


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
