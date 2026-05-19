import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.callbacks import adispatch_custom_event

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import get_conversation_history
from catchup.rag.nodes.utils import get_formatted_history_text
from catchup.rag.nodes.utils import log_node
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.rag.schemas.structures import VectorDbSearchPlan
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def generate_vector_queries_node(
    state: AgentState,
    llm: BaseChatModel,
    timeout: float | None = None,
):
    rewritten_query = state["rewritten_query"]
    global_context = state["global_context"].model_dump()

    messages = state.get("messages", [])
    recent_history = get_conversation_history(messages)[-4:]  # 직전 2턴
    recent_history_text = get_formatted_history_text(recent_history) if recent_history else ""
    slack_thread_context = state.get("slack_thread_context")

    prompt = prompt_loader.get_prompt(
        "rag/generate_vector_queries",
        query=rewritten_query,
        recent_history=recent_history_text,
        slack_thread_context=slack_thread_context,
        **global_context,
    )
    token_usages = {"token_breakdown": {}}
    structured_llm = llm.with_structured_output(
        VectorDbSearchPlan, method="function_calling", include_raw=True
    )

    await adispatch_custom_event(
        "process",
        {"status": "in_progress", "node": "generate_vector_queries"},
    )

    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=prompt,
            semaphore=rag_semaphores.llm_small,
            timeout=timeout,
        )
        plan: VectorDbSearchPlan = response.get("parsed")

    except RETRYABLE_ERRORS as e:
        raise e
    except Exception as e:
        logger.warning(
            "generate_vector_queries_node_failed",
            fallback="rewritten_query",
            error=str(e),
        )
        await adispatch_custom_event(
            "process",
            {
                "status": "completed",
                "node": "generate_vector_queries",
                "reasoning": "쿼리 생성에 실패해서 원래 질문으로 검색할게요.",
            },
        )
        return {
            "vector_search_queries": [
                VectorDbSearchQuery(
                    query=rewritten_query,
                    reasoning="Generation failed: using rewritten query as fallback.",
                )
            ],
        }

    queries = plan.queries[:1]

    await adispatch_custom_event(
        "process",
        {
            "status": "completed",
            "node": "generate_vector_queries",
            "reasoning": plan.reasoning or f"{len(queries)}개 검색 쿼리를 생성했어요.",
        },
    )

    _print_search_plan_log(plan)

    return {
        "vector_search_queries": queries,
        **token_usages,
    }


def _print_search_plan_log(plan: VectorDbSearchPlan):
    logger.debug(
        "vector_search_plan_generated",
        query_count=len(plan.queries),
        queries=[
            {
                "index": i,
                "query": q.query,
                "start_date": q.start_date.strftime("%Y-%m-%d %H:%M:%S")
                if q.start_date
                else None,
                "end_date": q.end_date.strftime("%Y-%m-%d %H:%M:%S")
                if q.end_date
                else None,
                "reasoning": q.reasoning,
            }
            for i, q in enumerate(plan.queries, 1)
        ],
    )
