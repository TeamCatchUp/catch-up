import logging

from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.factory import get_llm_service
from catchup.observability.langfuse_client import langfuse_handler
from catchup.rag.nodes.grade.prompt import DOCUMENT_GRADE_PROMPT
from catchup.rag.nodes.utils import get_latest_query, llm_semaphore
from catchup.rag.schemas import GradeDocuments
from catchup.rag.state import AgentState
from catchup.search.schemas import BaseSearchResult

logger = logging.getLogger(__name__)


async def grade_node(state: AgentState):
    logger.info("grade node 진입")
    llm_service = get_llm_service()
    llm = llm_service.get_llm()

    messages = state["messages"]

    # State에 저장된 current_query가 있다면 사용 (rewritten query 우선)
    question = state.get("current_query") or get_latest_query(messages)

    # retry는 최대 3번까지만 재시도
    if state.get("retry_count", 0) >= 3:
        return {"grade_status": "max_retries"}

    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])

    context_text = "\n\n".join(
        [doc.to_context_text(index=i) for i, doc in enumerate(retrieved_docs, start=1)]
    )

    if not context_text:
        return {"grade_status": "bad"}

    prompt = ChatPromptTemplate.from_template(DOCUMENT_GRADE_PROMPT)

    chain = prompt | llm.with_structured_output(
        GradeDocuments, method="function_calling"
    )

    async with llm_semaphore:
        answer = await chain.ainvoke(
            input={"question": question, "context": context_text},
            config={"callbacks": [langfuse_handler]},
        )

    is_relevant = answer.binary_score == "yes"

    return {"grade_status": "good" if is_relevant else "bad"}
