import structlog
from langchain_core.documents import Document

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.rag.nodes.utils import deduplicate_documents
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
async def search_vector_db_node(
    state: AgentState, vector_db_service: BaseVectorDbService
):

    queries = state.get("vector_search_queries", [])
    tool_filters = state.get("tool_filters", [])

    if not queries:
        logger.warning("no_search_plan_generated", fallback="rewritten_query")
        queries.append(
            VectorDbSearchQuery(
                query=state["rewritten_query"],
                reasoning="No generated queries found. Fallback to rewritten query.",
            )
        )

    try:
        query_dicts = [
            {
                "query": q.query,
                "start_date": q.start_date,
                "end_date": q.end_date,
                "keyword_tokens": q.keyword_tokens,
            }
            for q in queries
        ]
        results: list[list[Document]] = await vector_db_service.hybrid_search_batch(
            queries=query_dicts,
            k=100,
            weights=[0.6, 0.4],
            tool_filters=tool_filters,
        )
    except Exception as e:
        logger.warning(
            "search_vector_db_node_failed",
            fallback="empty_list",
            error=str(e),
            exc_info=True,
        )
        return {"retrieved_docs": []}

    flattened_results = [doc for sublist in results for doc in sublist]
    unique_results = deduplicate_documents(flattened_results)

    logger.info("search_results_fetched", count=len(unique_results))

    return {"retrieved_docs": unique_results}
