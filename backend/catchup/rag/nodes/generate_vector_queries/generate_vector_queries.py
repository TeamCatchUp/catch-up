import structlog
from langchain.chat_models import BaseChatModel

from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import ainvoke_llm_with_token_usage
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.structures import VectorDbSearchPlan
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def generate_vector_queries_node(state: AgentState, llm: BaseChatModel):
    rewritten_query = state["rewritten_query"]
    global_context = state["global_context"].model_dump()
    prompt = prompt_loader.get_prompt(
        "rag/generate_vector_queries",
        query=rewritten_query,
        **global_context
    )
    token_usages = {"token_breakdown": {}}
    structured_llm = llm.with_structured_output(
        VectorDbSearchPlan,
        method="function_calling",
        include_raw=True
    )

    try:
        response, token_usages = await ainvoke_llm_with_token_usage(
            llm=structured_llm,
            messages=prompt,
            semaphore=rag_semaphores.analysis
        )
        plan: VectorDbSearchPlan = response.get("parsed")
    
    except Exception as e:
        logger.warning(
            "generate_vector_queries_node_failed",
            fallback="rewritten_query",
            error=str(e)
        )
        fallback_query = VectorDbSearchQuery(
            query=rewritten_query,
            reasoning="Generation failed: using rewritten query as fallback."
        )
        return {
            "vector_search_queries": [fallback_query],
        }
    
    # simple 파이프라인은 단일 쿼리만 사용
    pipeline_plan = state.get("pipeline_plan")
    max_q = 1 if (pipeline_plan and pipeline_plan.pipeline_type == "simple") else len(plan.queries)
    queries = plan.queries[:max_q]

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
                "start_date": q.start_date.strftime('%Y-%m-%d %H:%M:%S') if q.start_date else None,
                "end_date": q.end_date.strftime('%Y-%m-%d %H:%M:%S') if q.end_date else None,
                "reasoning": q.reasoning,
            }
            for i, q in enumerate(plan.queries, 1)
        ],
    )
