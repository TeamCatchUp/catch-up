import logging

from langchain.messages import HumanMessage
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from catchup.components.llm.factory import get_llm_service, LlmProvider
from catchup.rag.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import (
    get_context_text_from_documents,
    llm_semaphore,
    log_node,
)
from catchup.rag.schemas.structures import GradeDocuments
from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)


@log_node
async def grade_node(state: AgentState):
    query = state["rewritten_query"]

    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    
    current_retry_count = state.get("retry_count", 0)

    if not retrieved_docs:
        logger.warning("검색된 문서가 없습니다. (grade_status='bad')")
        return {
            "grade_status": "bad",
            "grade_comment": "검색된 문서가 없습니다.",
            "retry_count": current_retry_count + 1
        }

    context_text = get_context_text_from_documents(retrieved_docs)

    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    structured_llm = llm.with_structured_output(
        GradeDocuments, method="function_calling"
    )

    prompt = prompt_loader.get_prompt(
        "grade",
        query=query,
        context=context_text
    )
    
    try:
        async with llm_semaphore:
            grade_result: GradeDocuments = await structured_llm.ainvoke(
                input=prompt
            )

    except Exception as e:
        logger.warning(f"Grade node failed: {e}")
        grade_result = GradeDocuments(
            binary_score="no",
            explanation=f"문서 유효성 검사 실패: {str(e)}"
        )

    is_relevant = grade_result.binary_score.lower().strip() == "yes"
    status = "good" if is_relevant else "bad"
    
    if status == "bad":
        new_retry_count = current_retry_count + 1
    else:
        new_retry_count = current_retry_count

    logger.info(f"Grade 결과: {status} (이유: {grade_result.explanation})")

    return {
        "grade_status": status,
        "grade_comment": grade_result.explanation,
        "retry_count": new_retry_count
    }
