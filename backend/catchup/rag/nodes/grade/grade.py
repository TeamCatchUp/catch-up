from typing import Literal

import structlog
from langchain.chat_models import BaseChatModel
from langchain_core.documents import Document

from catchup.costs.utils import extract_token_usages
from catchup.costs.utils import token_usage
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import log_node
from catchup.rag.nodes.utils import prepare_retrieved_context_text
from catchup.rag.schemas.structures import GradeDocuments
from catchup.rag.semaphores import rag_semaphores
from catchup.rag.state import AgentState

logger = structlog.get_logger()


@log_node
@token_usage
async def grade_node(state: AgentState, llm: BaseChatModel):
    query = state["rewritten_query"]
    retrieved_docs: list[Document] = state.get("retrieved_docs", [])
    current_retry_count = state.get("retry_count", 0)
    token_usages = {"token_breakdown": {}}

    if not retrieved_docs:
        logger.warning(
            "no_documents_retrieved", 
            grade_status="bad"
        )
        return {
            "grade_status": "bad",
            "grade_comment": "검색된 문서가 없습니다.",
            "retry_count": current_retry_count + 1,
        }

    context_text = prepare_retrieved_context_text(retrieved_docs)
    prompt = prompt_loader.get_prompt(
        "rag/grade",
        query=query,
        context=context_text
    )
    structured_llm = llm.with_structured_output(
        GradeDocuments,
        method="function_calling",
        include_raw=True
    )
    
    try:
        async with rag_semaphores.analysis:
            raw_response = await structured_llm.ainvoke(input=prompt)
            token_usages = extract_token_usages(raw_response.get("raw"))
            grade_result: GradeDocuments = raw_response.get("parsed")

    except Exception as e:
        logger.warning(
            "grade_node_failed",
            fallback="negative_binary_score",
            error=str(e),
            exc_info=True
        )
        grade_result = GradeDocuments(
            binary_score="no",
            explanation=f"document validation failed: {str(e)}"
        )

    status = _resolve_status(grade_result)
    retry_count = _resolve_retry_count(current_retry_count, status)  
    logger.debug(
        "grade_result",
        status=status,
        explanation=grade_result.explanation,
        resolved_retry_count=retry_count
    )

    return {
        "grade_status": status,
        "grade_comment": grade_result.explanation if status == "bad" else "",
        "retry_count": retry_count,
        **token_usages,
    }


def _resolve_status(grade_result: GradeDocuments) -> str:
    is_relevant = grade_result.binary_score.lower().strip() == "yes"
    return "good" if is_relevant else "bad"


def _resolve_retry_count(
    current_retry_count: int, 
    status: Literal["good", "bad"]
) -> int:
    if status == "bad":
        new_retry_count = current_retry_count + 1
    else:
        new_retry_count = current_retry_count
    return new_retry_count
