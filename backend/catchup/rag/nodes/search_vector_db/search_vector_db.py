import asyncio
import logging
from typing import Optional

from langchain_core.documents import Document

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.db.models import SourceType
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def search_vector_db_node(state: AgentState, vector_db_service: BaseVectorDbService):

    queries = state.get("vector_search_queries", [])
    tool_filters = state.get("tool_filters", [])

    if not queries:
        logger.warning("검색 계획 없음. rewritten query를 사용하여 검색 수행.")
        queries.append(VectorDbSearchQuery(
            query=state["rewritten_query"],
            reasoning="No generated queries found. Fallback to rewritten query."
        ))

    results: list[list[Document]] = await _get_hybrid_search_results(
        vector_db_service=vector_db_service,
        queries=queries,
        tool_filters=tool_filters,
        k=100,
        weights=[0.6, 0.4],
    )

    unique_results = _deduplicate_search_results(results)

    logger.info(f"검색 결과: {len(unique_results)} 개")

    return {"retrieved_docs": unique_results}


async def _get_hybrid_search_results(
    vector_db_service: BaseVectorDbService,
    queries: list[VectorDbSearchQuery],
    tool_filters: Optional[list[SourceType]],
    k: int = 10,
    weights: list[float] = [0.5, 0.5],
):
    tasks = [
        asyncio.to_thread(
            vector_db_service.hybrid_search,
            q.query,
            k,
            weights,
            tool_filters,
        )
        for q in queries
    ]
    results = await asyncio.gather(*tasks)

    return results


def _deduplicate_search_results(results: list[list[Document]]):
    unique_docs = {}
    for docs in results:
        for doc in docs:
            if doc.id not in unique_docs:
                unique_docs[doc.id] = doc
    final_docs = list(unique_docs.values())
    return final_docs
