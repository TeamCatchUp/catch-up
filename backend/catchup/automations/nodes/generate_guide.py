from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from catchup.automations.state import AutomationState
from catchup.prompts.loader import prompt_loader
from catchup.rag.nodes.utils import build_docs_summary

logger = structlog.get_logger(__name__)

_NO_DOCS_GUIDE = (
    "관련 참고 자료를 찾을 수 없습니다. "
    "담당자에게 직접 확인이 필요한 문의입니다."
)


async def generate_guide_node(state: AutomationState, llm: BaseChatModel) -> dict[str, Any]:
    """검색된 문서를 바탕으로 Slack 대응 가이드를 생성한다."""
    docs: list[Document] = state.get("retrieved_docs", [])
    if not docs:
        logger.warning("generate_guide_node_no_docs")
        return {"guide_text": _NO_DOCS_GUIDE}

    docs_summary = build_docs_summary(docs)
    inquiry_text = state["inquiry_text"]
    guide_instruction = state.get("guide_instruction")
    global_context = state["global_context"].model_dump()

    prompt = prompt_loader.get_prompt(
        "automations/generate_guide",
        inquiry_text=inquiry_text,
        docs_summary=docs_summary,
        guide_instruction=guide_instruction,
        **global_context,
    )

    response = await llm.ainvoke(prompt)
    guide_text: str = response.content

    logger.info("generate_guide_node_completed", guide_length=len(guide_text))
    return {"guide_text": guide_text}
