from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from catchup.automations.state import AutomationState
from catchup.automations.structures import GradeResult
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import build_docs_summary

logger = structlog.get_logger(__name__)

_NO_DOCS_RESULT: GradeResult = {
    "reusable": False,
    "reason": "No similar cases retrieved.",
}

async def grade_node(state: AutomationState, llm: BaseChatModel) -> dict[str, Any]:
    """유사 사례 문서를 읽고 재활용 가능 여부를 판단한다."""
    docs: list[Document] = state.get("retrieved_docs", [])
    if not docs:
        logger.info("grade_node_skipped", reason="no_docs")
        return {"grade_result": _NO_DOCS_RESULT}

    docs_summary = build_docs_summary(docs)
    inquiry_text = state["inquiry_text"]

    prompt = prompt_loader.get_prompt(
        "automations/grade",
        inquiry_text=inquiry_text,
        docs_summary=docs_summary,
    )

    structured_llm = llm.with_structured_output(GradeResult)
    output = await structured_llm.ainvoke(prompt)

    if isinstance(output, dict):
        grade_result: GradeResult = {
            "reusable": output["reusable"],
            "reason": output["reason"],
        }
    else:
        grade_result = {
            "reusable": output.reusable,
            "reason": output.reason,
        }

    logger.info(
        "grade_node_completed",
        reusable=grade_result["reusable"],
        reason=grade_result["reason"],
    )
    return {"grade_result": grade_result}
