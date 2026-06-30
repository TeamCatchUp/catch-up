from datetime import datetime
from datetime import timezone

import structlog
from langchain.chat_models import BaseChatModel

from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.semaphores import rag_semaphores
from catchup.schemas.context import GlobalCurrentTimeContext
from catchup.schemas.sources import SOURCE_METADATA
from catchup.schemas.structures import ManualSearchQuery
from catchup.search.planner.state import _QUERY_CACHE_MAX_SIZE
from catchup.search.planner.state import CachedSearch
from catchup.search.planner.state import ManualSearchState

logger = structlog.get_logger()

_CACHE_TTL_HOURS = 12


@log_node
async def plan_manual_search_node(
    state: ManualSearchState,
    llm: BaseChatModel,
    timeout: float | None = None,
) -> dict:
    original_query = state["original_query"]
    query_cache: dict[str, CachedSearch] = dict(
        state.get("query_cache") or {}
    )

    if original_query in query_cache:
        cached = query_cache[original_query]
        if isinstance(cached, CachedSearch):
            age = datetime.now(timezone.utc) - cached.generated_at
            if age.total_seconds() < _CACHE_TTL_HOURS * 3600:
                logger.debug(
                    "plan_manual_search_cache_hit", query=original_query
                )
                # LRU: 끝으로 이동. searched_at은 이번 검색 시각으로 갱신,
                # generated_at은 LLM 호출 시각이므로 보존.
                query_cache.pop(original_query)
                query_cache[original_query] = CachedSearch(
                    planned=cached.planned,
                    searched_at=datetime.now(timezone.utc),
                    generated_at=cached.generated_at,
                )
                return {"query_cache": query_cache, "query_cache_hit": True}

    current_time = GlobalCurrentTimeContext()
    prompt = prompt_loader.get_prompt(
        "search/plan_manual_search",
        query=original_query,
        current_time=current_time,
        sources=list(SOURCE_METADATA.values()),
    )
    structured_llm = llm.with_structured_output(
        ManualSearchQuery, method="function_calling", include_raw=True
    )

    try:
        response, _ = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=prompt,
            semaphore=rag_semaphores.llm_small,
            timeout=timeout,
        )
        planned: ManualSearchQuery = response.get("parsed")

    except RETRYABLE_ERRORS as e:
        raise e
    except Exception:
        logger.warning(
            "plan_manual_search_llm_failed",
            fallback="raw_query",
            query=original_query,
        )
        planned = ManualSearchQuery(
            query=original_query,
            keyword_tokens=[],
            reasoning="LLM failed; using raw query as fallback.",
        )

    logger.debug(
        "plan_manual_search_result",
        original_query=original_query,
        planned_query=planned.query,
        keyword_tokens=planned.keyword_tokens,
        inferred_tool_filters=planned.inferred_tool_filters,
        start_date=planned.start_date,
        end_date=planned.end_date,
    )

    if len(query_cache) >= _QUERY_CACHE_MAX_SIZE:
        query_cache.pop(next(iter(query_cache)))  # LRU 제거
    now = datetime.now(timezone.utc)
    query_cache[original_query] = CachedSearch(
        planned=planned, searched_at=now, generated_at=now
    )

    return {"query_cache": query_cache, "query_cache_hit": False}
