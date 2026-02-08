import logging

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.nodes.grade.prompt import DOCUMENT_GRADE_PROMPT
from catchup.rag.nodes.utils import (
    get_context_text_from_documents,
    llm_semaphore,
    log_node,
)
from catchup.rag.schemas import GradeDocuments
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def grade_node(state: AgentState):
    query = state["rewritten_query"]

    retrieved_docs: list[Document] = state.get("retrieved_docs", [])

    if not retrieved_docs:
        logger.warning("검색된 문서가 없습니다. (grade_status='bad')")
        return {"grade_status": "bad", "grade_comment": "검색된 문서가 없습니다."}

    context_text = get_context_text_from_documents(retrieved_docs)

    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    prompt = ChatPromptTemplate.from_template(DOCUMENT_GRADE_PROMPT)
    chain = prompt | llm.with_structured_output(
        GradeDocuments, method="function_calling"
    )

    try:
        async with llm_semaphore:
            grade_result: GradeDocuments = await chain.ainvoke(
                input={"query": query, "context": context_text}
            )

    except Exception as e:
        logger.warning(f"Grade node failed: {e}")
        grade_result = GradeDocuments(
            binary_score="yes", explanation=f"문서 유효성 검사 실패: {str(e)}"
        )

    is_relevant = grade_result.binary_score.lower().strip() == "yes"
    status = "good" if is_relevant else "bad"

    logger.info(f"Grade 결과: {status} (이유: {grade_result.explanation})")

    return {"grade_status": status, "grade_comment": grade_result.explanation}
