from collections import Counter

import structlog

from catchup.components.vector_db.pgvector.pgvector import PGBigmRetriever
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.configs.config import settings
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.langfuse.configs import get_observe
from catchup.rag.checkpoint import get_langgraph_checkpointer
from catchup.rag.nodes.utils import build_doc_groups
from catchup.rag.schemas.sources import BaseSource
from catchup.search.planner.graph import get_search_planner_graph

logger = structlog.get_logger()

observe = get_observe()

_MANUAL_SEARCH_POOL_SIZE: int = 50


class ManualSearchService:
    def __init__(self):
        self._app = None

    def _get_planner(self):
        if self._app is None:
            checkpointer = get_langgraph_checkpointer()
            self._app = get_search_planner_graph(checkpointer)
        return self._app

    def _setup_config(self, user_id: int) -> tuple[dict, dict]:
        base_config = {"configurable": {"thread_id": f"search:{user_id}"}}
        invoke_config = {**base_config}

        if settings.ENABLE_LANGFUSE:
            from langfuse.langchain import CallbackHandler

            if client := get_langfuse_client():
                trace_id = client.get_current_trace_id()
                invoke_config["callbacks"] = [
                    CallbackHandler(trace_context={"trace_id": trace_id})
                ]

        return base_config, invoke_config

    @observe(name="manual-search")
    async def search(
        self,
        user: User,
        keyword: str,
        tool_filters: list[SourceType] | None,
        vector_db_service: PGVectorService,
    ) -> tuple[list[BaseSource], int, dict[str, int]]:
        planner = self._get_planner()
        _, invoke_config = self._setup_config(user.id)

        if settings.ENABLE_LANGFUSE:
            from langfuse import propagate_attributes

            with propagate_attributes(
                metadata={
                    "user_id": str(user.id),
                    "name": user.name,
                    "department": user.department,
                }
            ):
                state = await planner.ainvoke(
                    {"original_query": keyword}, config=invoke_config
                )
        else:
            state = await planner.ainvoke(
                {"original_query": keyword}, config=invoke_config
            )

        planned = state["query_cache"][keyword]

        if getattr(planned, "search_mode", "hybrid") == "keyword_only":
            retriever = PGBigmRetriever(
                session_factory=vector_db_service.session_factory,
                async_session_factory=vector_db_service.async_session_factory,
                collection_name=vector_db_service.collection_name,
                k=_MANUAL_SEARCH_POOL_SIZE,
                offset=0,
                tool_filters=tool_filters,
                search_mode="fuzzy",
            )
            all_docs = await retriever.async_invoke(planned.keyword_tokens)
        else:
            all_docs = await vector_db_service.hybrid_search(
                query=planned.query,
                k=_MANUAL_SEARCH_POOL_SIZE,
                tool_filters=tool_filters,
                keyword_tokens=planned.keyword_tokens or None,
                offset=0,
            )

        groups = build_doc_groups(all_docs)
        deduped_docs = [g.representative for g in groups]

        total = len(deduped_docs)
        source_distribution = dict(
            Counter(doc.metadata.get("source", "unknown") for doc in deduped_docs)
        )

        logger.debug(
            "manual_search_completed",
            raw_count=len(all_docs),
            deduped_count=total,
            source_distribution=source_distribution,
        )

        results = [
            BaseSource.from_document(
                index=i + 1,
                doc=doc,
                relevance_score=doc.metadata.get("score", 0.0),
            )
            for i, doc in enumerate(deduped_docs)
        ]

        return results, total, source_distribution
