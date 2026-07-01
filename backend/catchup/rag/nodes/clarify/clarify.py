import asyncio

import structlog
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage

from catchup.rag.constants import FALLBACK_ANSWER
from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState

logger = structlog.get_logger()

_TOKEN_DELAY_SEC = 0.025  # 단어 사이 간격 (ms 단위 LLM 체감 속도와 유사)


@log_node
async def clarify_node(state: AgentState):
    """Supervisor가 생성한 명확화 질문을 단어 단위로 스트리밍한다. LLM 호출 없음."""
    pipeline_plan = state.get("pipeline_plan")
    question = pipeline_plan.clarification_question if pipeline_plan else None

    if not question:
        logger.warning("clarify_node_missing_question", fallback="fallback_answer")
        question = FALLBACK_ANSWER

    logger.info("clarify_question_sent", question=question)

    words = question.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else f" {word}"
        await adispatch_custom_event("clarify_token", {"token": token})
        await asyncio.sleep(_TOKEN_DELAY_SEC)

    return {
        "messages": [AIMessage(content=question)],
        "sources": [],
    }
