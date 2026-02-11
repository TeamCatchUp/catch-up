import logging

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import llm_semaphore, log_node
from catchup.rag.schemas.structures import VectorDbSearchPlan, VectorDbSearchQuery
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def generate_vector_queries_node(state: AgentState):
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    structured_llm = llm.with_structured_output(
        VectorDbSearchPlan, method="function_calling"
    )
        
    rewritten_query = state["rewritten_query"]
    
    global_context = state["global_context"].model_dump()
    
    prompt = prompt_loader.get_prompt(
        "generate_vector_queries",
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
            f"Vector query를 생성하는 데 실패했습니다. 재작성된 쿼리를 사용합니다.: {e}"
        )
        fallback_query = VectorDbSearchQuery(
            query=rewritten_query,
            reasoning="Generation failed: using rewritten query as fallback."
        )
        return {"vector_search_queries": [fallback_query]}

    return {"vector_search_queries": plan.queries}


def _print_search_plan_log(plan: VectorDbSearchPlan):
    log_msg_lines = [f"[Vector Search Plan] Generated {len(plan.queries)} queries:"]
    for i, q in enumerate(plan.queries, 1):
        log_msg_lines.append(f'   {i}. "{q.query}"\n      - 이유: {q.reasoning}')
    logger.info("\n".join(log_msg_lines))
