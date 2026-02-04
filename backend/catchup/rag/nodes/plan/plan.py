import logging

from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.service import LlmProvider
from catchup.components.llm.factory import get_llm_service
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.plan.prompt import PLANNER_PROMPT
from catchup.rag.nodes.utils import get_latest_query, llm_semaphore
from catchup.rag.schemas import SearchPlan
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


async def plan_node(state: AgentState):
    logger.info("plan node 진입")
    llm_service = get_llm_service(LlmProvider.OPENAI)
    llm = llm_service.get_llm()

    current_query = state.get("current_query") or get_latest_query(state["messages"])

    structured_llm = llm.with_structured_output(SearchPlan, method="function_calling")

    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)

    chain = prompt | structured_llm

    async with llm_semaphore:
        plan: SearchPlan = await chain.ainvoke(
            input={"current_query": current_query},
            config={"callbacks": [langfuse_handler]},
        )

    for q in plan.queries:
        logger.info(f"query plan: [{q.datasource}] {q.query}")

    return {"search_queries": plan.queries}
