from __future__ import annotations

import html
from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from catchup.automations.state import AutomationState
from catchup.automations.structures import GuideDraft
from catchup.langgraph.retry import RETRYABLE_ERRORS
from catchup.prompts.loader import prompt_loader
from catchup.schemas.sources import BaseSource
from catchup.utils.documents import build_doc_groups
from catchup.utils.documents import render_grouped_context_text

logger = structlog.get_logger(__name__)

_MAX_CITATION_ITEMS = 5

_NO_DOCS_RESULT: dict[str, Any] = {
    "guide_text": "",
    "guide_explanation": (
        "관련 참고 자료를 찾을 수 없습니다. "
        "담당자에게 직접 확인이 필요한 문의입니다."
    ),
    "citations": [],
}


async def generate_guide_node(state: AutomationState, llm: BaseChatModel) -> dict[str, Any]:
    """검색된 문서를 바탕으로 응대 가이드(초안/설명/근거)를 생성한다."""
    docs: list[Document] = state.get("retrieved_docs", [])
    if not docs:
        logger.warning("generate_guide_node_no_docs")
        return _NO_DOCS_RESULT

    doc_groups = build_doc_groups(docs)
    docs_summary = render_grouped_context_text(doc_groups)
    # HTML-entity-escape하여 <, >를 무력화한다 — 고객 문의에 가짜 닫는 태그를 심어
    # customer_inquiry 블록을 탈출하려는 프롬프트 인젝션을 막는다.
    inquiry_text = html.escape(state["inquiry_text"], quote=False)
    guide_instruction = state.get("guide_instruction")
    global_context = state["global_context"].model_dump()

    prompt = prompt_loader.get_prompt(
        "automations/generate_guide",
        inquiry_text=inquiry_text,
        docs_summary=docs_summary,
        guide_instruction=guide_instruction,
        **global_context,
    )

    structured_llm = llm.with_structured_output(GuideDraft)
    try:
        output = await structured_llm.ainvoke(prompt)
    except RETRYABLE_ERRORS:
        raise

    if isinstance(output, dict):
        guide_draft = GuideDraft(
            draft=output["draft"],
            explanation=output["explanation"],
            cited_indices=output.get("cited_indices", []),
        )
    else:
        guide_draft = GuideDraft(
            draft=output.draft,
            explanation=output.explanation,
            cited_indices=output.cited_indices,
        )

    cited_groups = [
        group for group in doc_groups if group.display_index in guide_draft.cited_indices
    ] or doc_groups[:_MAX_CITATION_ITEMS]
    citations: list[BaseSource] = [
        BaseSource.from_document(group.display_index, group.representative, is_cited=True)
        for group in cited_groups
    ]

    logger.info(
        "generate_guide_node_completed",
        draft_length=len(guide_draft.draft),
        citation_count=len(citations),
    )
    return {
        "guide_text": guide_draft.draft,
        "guide_explanation": guide_draft.explanation,
        "citations": citations,
    }
