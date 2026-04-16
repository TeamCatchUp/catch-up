import asyncio

import structlog
from langchain_core.documents import Document

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.db.models import SourceType
from catchup.rag.executors import rag_executors
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.filters import build_temporal_filters
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
async def search_vector_db_node(state: AgentState, vector_db_service: BaseVectorDbService):

    queries = state.get("vector_search_queries", [])
    tool_filters = state.get("tool_filters", [])

    if not queries:
        logger.warning(
            "no_search_plan_generated", 
            fallback="rewritten_query"
        )
        queries.append(VectorDbSearchQuery(
            query=state["rewritten_query"],
            reasoning="No generated queries found. Fallback to rewritten query."
        ))
    
    try:
        results: list[list[Document]] = await _get_hybrid_search_results(
            vector_db_service=vector_db_service,
            queries=queries,
            tool_filters=tool_filters,
            k=100,
            weights=[0.6, 0.4],
        )
    except Exception as e:
        logger.warning(
            "search_vector_db_node_failed",
            fallback="empty_list",
            error=str(e),
            exc_info=True
        )
        return {"retrieved_docs": []}

    unique_results = _deduplicate_search_results(results)

    logger.info(
        "search_results_fetched",
        count=len(unique_results)
    )

    return {"retrieved_docs": unique_results}


async def _get_hybrid_search_results(
    vector_db_service: BaseVectorDbService,
    queries: list[VectorDbSearchQuery],
    tool_filters: list[SourceType] | None = None,
    k: int = 10,
    weights: list[float] = [0.5, 0.5],
):
    
    loop = asyncio.get_running_loop()
    tasks = []

    for q in queries:
        temporal_filters = build_temporal_filters(
            tool_filters=tool_filters,
            start_date=q.start_date,
            end_date=q.end_date
        )

        tasks.append(
            loop.run_in_executor(
                rag_executors.vector_search,
                vector_db_service.hybrid_search,
                q.query,
                k,
                weights,
                tool_filters,
                temporal_filters,
            )
        )

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
