from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog

from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.configs.config import settings
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.langfuse.configs import get_observe
from catchup.rag.checkpoint import get_langgraph_checkpointer
from catchup.rag.nodes.utils import build_doc_groups
from catchup.schemas.sources import BaseSource
from catchup.search.filters import build_manual_search_temporal_filters
from catchup.search.planner.graph import get_search_planner_graph
from catchup.search.planner.state import CachedSearch

logger = structlog.get_logger()


def resolve(
    smart_filter: bool,
    explicit: list | None,
    inferred: list | None,
) -> list | None:
    """협업 툴 필터 resolve 함수. explicit가 falsy면 inferred 허용 여부를 판단한다."""
    if explicit:
        return explicit
    if not smart_filter:
        return None
    if inferred:
        return inferred
    return None


@dataclass
class SearchResult:
    """manual search 결과를 담는 데이터클래스."""

    results: list[BaseSource]
    total: int
    source_distribution: dict[str, int]
    effective_tool_filters: list[SourceType] | None
    effective_start_date: datetime | None
    effective_end_date: datetime | None
    is_tool_filter_inferred: bool
    is_date_filter_inferred: bool


observe = get_observe()

_MANUAL_SEARCH_POOL_SIZE: int = 70


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
        smart_filter: bool = False,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> SearchResult:
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

        planned = state["query_cache"][keyword].planned

        resolved_tool_filters = resolve(
            smart_filter, tool_filters, planned.inferred_tool_filters
        )

        # 날짜는 start/end pair 단위로 resolve한다 — 독립 resolve 금지
        # UI에서 start 또는 end 중 하나라도 지정했으면 UI pair 우선
        explicit_date = start_date or end_date
        if explicit_date:
            resolved_start, resolved_end = start_date, end_date
        elif not smart_filter:
            resolved_start, resolved_end = None, None
        else:
            resolved_start, resolved_end = planned.start_date, planned.end_date

        is_tool_filter_inferred = (
            smart_filter
            and not tool_filters
            and planned.inferred_tool_filters is not None
        )
        is_date_filter_inferred = (
            smart_filter
            and not explicit_date
            and (planned.start_date is not None or planned.end_date is not None)
        )

        temporal_filters = build_manual_search_temporal_filters(
            tool_filters=resolved_tool_filters,
            start_date=resolved_start,
            end_date=resolved_end,
        ) or None

        all_docs = await vector_db_service.hybrid_search(
            query=planned.query,
            k=_MANUAL_SEARCH_POOL_SIZE,
            tool_filters=resolved_tool_filters,
            keyword_tokens=planned.keyword_tokens or None,
            offset=0,
            temporal_filters=temporal_filters,
            score_threshold=0.3,
            use_title_filter=True,
        )

        groups = build_doc_groups(all_docs)
        deduped_docs = sorted(
            (g.representative for g in groups),
            key=lambda d: d.metadata.get("score", 0.0),
            reverse=True,
        )

        total = len(deduped_docs)
        source_distribution = dict(
            Counter(doc.metadata.get("source", "unknown") for doc in deduped_docs)
        )

        logger.debug(
            "manual_search_completed",
            raw_count=len(all_docs),
            deduped_count=total,
            source_distribution=source_distribution,
            effective_tool_filters=resolved_tool_filters,
            is_tool_filter_inferred=is_tool_filter_inferred,
            is_date_filter_inferred=is_date_filter_inferred,
        )

        results = [
            BaseSource.from_document(
                index=i + 1,
                doc=doc,
                relevance_score=doc.metadata.get("score", 0.0),
            )
            for i, doc in enumerate(deduped_docs)
        ]

        return SearchResult(
            results=results,
            total=total,
            source_distribution=source_distribution,
            effective_tool_filters=resolved_tool_filters,
            effective_start_date=resolved_start,
            effective_end_date=resolved_end,
            is_tool_filter_inferred=is_tool_filter_inferred,
            is_date_filter_inferred=is_date_filter_inferred,
        )

    async def get_search_history(
        self,
        user: User,
        period: str,
    ) -> list[tuple[str, datetime]]:
        """query_cache에서 period 기준으로 필터링한 최근 검색어를 최신순으로 반환한다."""
        planner = self._get_planner()
        base_config, _ = self._setup_config(user.id)
        snapshot = await planner.aget_state(base_config)

        if not snapshot or not snapshot.values:
            return []

        query_cache: dict[str, CachedSearch] = snapshot.values.get("query_cache") or {}
        now = datetime.now(timezone.utc)

        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "7d":
            cutoff = now - timedelta(days=7)
        else:
            cutoff = None

        entries = [
            (query, entry.searched_at)
            for query, entry in query_cache.items()
            if isinstance(entry, CachedSearch)
            and (cutoff is None or entry.searched_at >= cutoff)
        ]
        return list(reversed(entries))
