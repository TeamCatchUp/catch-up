import time
from copy import deepcopy

import structlog
from langchain_core.documents import Document

from catchup.components.reranker.service import BaseRerankService
from catchup.configs.config import settings
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()

MAX_RERANK_DOCUMENT_TEXT_LENGTH = 30_000


@log_node
async def rerank_node(
    state: AgentState, rerank_service: BaseRerankService
) -> dict:
    """문서 목록을 reranker로 재정렬해 반환한다.

    validate → rerank 서비스 호출만 담당한다.
    K 선정과 에이전틱 후처리는 select_final_docs_node가 담당한다.
    """
    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    if not retrieved_docs:
        logger.warning("no_documents_retrieved")
        return {"retrieved_docs": [], "rerank_count": 0}

    rerank_count: int = state.get("rerank_count", 0)
    query = state["rewritten_query"]

    retrieved_docs = _validate_retrieved_docs(retrieved_docs)

    try:
        t_sem = time.perf_counter()
        logger.debug(
            "semaphore_acquiring",
            semaphore="reranker",
            doc_count=len(retrieved_docs),
        )
        async with rag_semaphores.reranker:
            t_rerank = time.perf_counter()
            logger.debug(
                "rerank_invoke_start",
                semaphore_wait_elapsed=round(t_rerank - t_sem, 3),
                doc_count=len(retrieved_docs),
            )
            reranked_docs = await rerank_service.rerank(
                query=query,
                documents=retrieved_docs,
                top_n=settings.RERANK_TOP_N,
            )
            logger.debug(
                "rerank_invoke_completed",
                elapsed=round(time.perf_counter() - t_rerank, 3),
            )
    except RETRYABLE_ERRORS:
        raise
    except Exception as e:
        logger.warning(
            "rerank_node_failed",
            fallback="original_order",
            error=str(e),
            exc_info=True,
        )
        return {
            "retrieved_docs": retrieved_docs,
            "rerank_count": 0,
        }

    return {
        "retrieved_docs": reranked_docs,
        "rerank_count": rerank_count + 1,
    }


def _validate_retrieved_docs(
    retrieved_docs: list[Document],
) -> list[Document]:
    """AWS Bedrock Cohere Rerank 3.5의 본문 길이 제한에 맞게 문서를 검증한다."""
    valid_docs = []
    for doc in retrieved_docs:
        content = doc.page_content
        if len(content) <= MAX_RERANK_DOCUMENT_TEXT_LENGTH:
            valid_docs.append(doc)
            continue
        truncated_doc = deepcopy(doc)
        truncated_doc.page_content = content[:MAX_RERANK_DOCUMENT_TEXT_LENGTH]
        valid_docs.append(truncated_doc)
    return valid_docs
