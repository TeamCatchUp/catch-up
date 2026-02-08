import logging

from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.nodes.generate_vector_queries.prompt import (
    VECTOR_QUERIES_GENERATION_PROMPT,
)
from catchup.rag.nodes.utils import llm_semaphore, log_node
from catchup.rag.schemas import VectorDbSearchPlan
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def generate_vector_queries_node(state: AgentState):
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    structured_llm = llm.with_structured_output(
        VectorDbSearchPlan, method="function_calling"
    )
    prompt = ChatPromptTemplate.from_template(VECTOR_QUERIES_GENERATION_PROMPT)
    chain = prompt | structured_llm

    rewritten_query = state["rewritten_query"]

    try:
        async with llm_semaphore:
            plan: VectorDbSearchPlan = await chain.ainvoke(
                input={"rewritten_query": rewritten_query}
            )

        _print_search_plan_log(plan)

    except Exception as e:
        logger.warning(
            f"Vector query를 생성하는 데 실패했습니다. 재작성된 쿼리를 사용합니다.: {e}"
        )
        return {"vector_search_queries": [state["rewritten_query"]]}

    return {"vector_search_queries": plan.queries}


def _print_search_plan_log(plan: VectorDbSearchPlan):
    log_msg_lines = [f"[Vector Search Plan] Generated {len(plan.queries)} queries:"]
    for i, q in enumerate(plan.queries, 1):
        log_msg_lines.append(f'   {i}. "{q.query}"\n      - 이유: {q.reasoning}')
    logger.info("\n".join(log_msg_lines))
