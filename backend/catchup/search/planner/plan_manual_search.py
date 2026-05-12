import structlog
from langchain.chat_models import BaseChatModel

from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.semaphores import rag_semaphores
from catchup.search.planner.state import ManualSearchState

logger = structlog.get_logger()


@log_node
async def plan_manual_search_node(
    state: ManualSearchState,
    llm: BaseChatModel,
    timeout: float | None = None,
) -> dict:
    original_query = state["original_query"]
    last_planned_query = state.get("last_planned_query", "")
    planned_search = state.get("planned_search")

    if original_query == last_planned_query and planned_search is not None:
        logger.debug("plan_manual_search_cache_hit", query=original_query)
        return {}

    prompt = prompt_loader.get_prompt("search/plan_manual_search", query=original_query)
    structured_llm = llm.with_structured_output(
        VectorDbSearchQuery, method="function_calling", include_raw=True
    )

    try:
        response, _ = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=prompt,
            semaphore=rag_semaphores.llm_small,
            timeout=timeout,
        )
        planned: VectorDbSearchQuery = response.get("parsed")

    except RETRYABLE_ERRORS as e:
        raise e
    except Exception:
        logger.warning(
            "plan_manual_search_llm_failed",
            fallback="raw_query",
            query=original_query,
        )
        planned = VectorDbSearchQuery(
            query=original_query,
            keyword_tokens=[],
            reasoning="LLM failed; using raw query as fallback.",
        )

    logger.debug(
        "plan_manual_search_result",
        original_query=original_query,
        planned_query=planned.query,
        keyword_tokens=planned.keyword_tokens,
    )

    return {
        "last_planned_query": original_query,
        "planned_search": planned,
    }
