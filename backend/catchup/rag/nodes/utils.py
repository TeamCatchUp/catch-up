# llm 호출 Rate Limit 방어
import asyncio
import functools
import logging
import time
from typing import Callable, Awaitable, Annotated

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.message import add_messages

# Semaphores (Rate limit 방어용)
llm_semaphore = asyncio.Semaphore(10)
rerank_semaphore = asyncio.Semaphore(10)

# 사용자-어시스턴트 대화 전처리 함수들
def filter_conversation(messages: Annotated[list, add_messages]):
    return [
        m for m in messages 
        if isinstance(m, (HumanMessage, AIMessage))
    ]


def get_conversation_history(messages: Annotated[list, add_messages]):
    filtered_messages = filter_conversation(messages)
    return filtered_messages[:-1][-6:]


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )


def get_context_text_from_documents(documents: list[Document]):
    return "\n\n".join([
        f"[{i}] (Source: {doc.metadata.get('source_type', 'unknown')})\n{doc.page_content}" 
        for i, doc in enumerate(documents, start=1)
    ])


# node 로깅 데코레이터
logger = logging.getLogger("catchup.graph")

def log_node(func: Callable[..., Awaitable[dict]]):
    """
    LangGraph 노드 실행 전후로 로깅을 수행하는 데코레이터
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        
        node_name = func.__name__
        start_time = time.time()
        
        logger.info(f"[START] Node: {node_name} started.")
        
        try:
            result = await func(*args, **kwargs)
            
            elapsed = time.time() - start_time
            logger.info(f"[END] Node: {node_name} completed. ({elapsed:.2f}s)")
            
            return result
            
        except Exception as e:
            logger.error(f"Node: {node_name} failed: {e}", exc_info=True)
            raise e

    return wrapper