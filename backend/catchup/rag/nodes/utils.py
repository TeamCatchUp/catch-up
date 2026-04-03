import functools
import time
from typing import Annotated
from typing import Awaitable
from typing import Callable

import structlog
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages


# 사용자-어시스턴트 대화 전처리 함수들
def filter_conversation(messages: Annotated[list, add_messages]):
    return [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]


def get_conversation_history(messages: Annotated[list, add_messages]):
    filtered_messages = filter_conversation(messages)
    return filtered_messages[:-1][-6:]


def get_latest_query(messages: Annotated[list, add_messages]):
    return next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )


def prepare_context_text(documents: list[Document]) -> str:
    parts = []
    for i, doc in enumerate(documents, start=1):
        source = doc.metadata.get("source", "unknown")
        content = doc.metadata.get("contextual_content", "")
        temporal = resolve_temporal_context(doc.metadata) 
        parts.append(f"[{i}] (Source: {source})\n{content} {temporal}")
    return "\n\n".join(parts)


def resolve_temporal_context(metadata: dict) -> str:
    temporal_fields = [
        "created_at", 
        "updated_at",
        "resolved_at",
        "due_date",
        "edited_at",
        "closed_at",
        "merged_at",
        "committed_at",
    ]
    
    parts = [
        f"{field}: {str(metadata[field])}"
        for field in temporal_fields
        if metadata.get(field)
    ]
    
    return " | ".join(parts) if parts else ""
    

def extract_anchor_ids(documents: list[Document]) -> list[str]:
    anchors = [doc.id for doc in documents if doc.id]
    return list(dict.fromkeys(anchors))  # 중복 제거 & 순서 유지


# node 로깅 데코레이터
logger = structlog.get_logger("catchup.graph")


def log_node(func: Callable[..., Awaitable[dict]]):
    """
    LangGraph 노드 실행 전후로 로깅을 수행하는 데코레이터
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):

        node_name = func.__name__
        start_time = time.perf_counter()

        logger.info(
            "node_started",
            node_name=node_name
        )

        try:
            result = await func(*args, **kwargs)

            elapsed = time.perf_counter() - start_time
            logger.info(
                "node_completed",
                node_name=node_name,
                duration=round(elapsed, 4)
            )

            return result

        except Exception as e:
            logger.error(
                "node_failed",
                node_name=node_name,
                error=str(e),
                exc_info=True
            )
            raise e

    return wrapper
