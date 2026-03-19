import structlog
from langchain.chat_models import BaseChatModel

from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import llm_semaphore
from catchup.rag.nodes.utils import log_node
from catchup.rag.schemas.structures import VectorDbSearchPlan
from catchup.rag.schemas.structures import VectorDbSearchQuery
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
async def generate_vector_queries_node(state: AgentState, llm: BaseChatModel):
    structured_llm = llm.with_structured_output(
        VectorDbSearchPlan,
        method="function_calling"
    )
        
    rewritten_query = state["rewritten_query"]
    
    global_context = state["global_context"].model_dump()
    
    prompt = prompt_loader.get_prompt(
        "rag/generate_vector_queries",
        query=rewritten_query,
        **global_context
    )

    try:
        async with llm_semaphore:
            plan: VectorDbSearchPlan = await structured_llm.ainvoke(
                input=prompt
            )

        _print_search_plan_log(plan)

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
        return {"vector_search_queries": [fallback_query]}

    return {"vector_search_queries": plan.queries}


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
