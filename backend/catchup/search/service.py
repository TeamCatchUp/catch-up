import structlog

from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.models import SourceType
from catchup.rag.checkpoint import get_langgraph_checkpointer
from catchup.rag.schemas.sources import BaseSource
from catchup.search.planner.graph import get_search_planner_graph

logger = structlog.get_logger()


class ManualSearchService:
    def __init__(self):
        self._app = None

    def _get_planner(self):
        if self._app is None:
            checkpointer = get_langgraph_checkpointer()
            self._app = get_search_planner_graph(checkpointer)
        return self._app

    async def search(
        self,
        user_id: int,
        keyword: str,
        limit: int,
        offset: int,
        tool_filters: list[SourceType] | None,
        vector_db_service: PGVectorService,
    ) -> list[BaseSource]:
        planner = self._get_planner()
        thread_id = f"search:{user_id}"

        state = await planner.ainvoke(
            {"original_query": keyword},
            config={"configurable": {"thread_id": thread_id}},
        )
        planned = state["planned_search"]

        docs = await vector_db_service.hybrid_search(
            query=planned.query,
            k=limit,
            tool_filters=tool_filters,
            keyword_tokens=planned.keyword_tokens or None,
            offset=offset,
        )

        return [
            BaseSource.from_document(
                index=i + 1,
                doc=doc,
                relevance_score=doc.metadata.get("score", 0.0),
            )
            for i, doc in enumerate(docs)
        ]
