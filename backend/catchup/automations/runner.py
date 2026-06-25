from __future__ import annotations

from dataclasses import dataclass

import structlog
from langchain_core.messages import HumanMessage

from catchup.automations.graph import get_inquiry_automation_graph
from catchup.automations.state import AutomationState
from catchup.db.models import SourceType
from catchup.rag.schemas.context import GlobalContext

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AutomationInput:
    inquiry_text: str
    user_chat_id: str
    slack_channel_id: str
    slack_credential_id: int
    global_context: GlobalContext
    guide_instruction: str | None = None
    quiet_period_seconds: int | None = None


async def run_inquiry_automation(automation_input: AutomationInput) -> None:
    """Channel Talk 문의 자동화 파이프라인을 실행한다."""
    logger.info(
        "inquiry_automation_started",
        user_chat_id=automation_input.user_chat_id,
        workspace_id=automation_input.global_context.workspace.id,
    )

    state = AutomationState(
        inquiry_text=automation_input.inquiry_text,
        user_chat_id=automation_input.user_chat_id,
        slack_channel_id=automation_input.slack_channel_id,
        slack_credential_id=automation_input.slack_credential_id,
        global_context=automation_input.global_context,
        guide_instruction=automation_input.guide_instruction,
        quiet_period_seconds=automation_input.quiet_period_seconds,
        messages=[HumanMessage(content=automation_input.inquiry_text)],
        rewritten_query=automation_input.inquiry_text,
        vector_search_queries=[],
        retrieved_docs=[],
        tool_filters=[SourceType.CHANNEL_TALK],
        rerank_count=0,
        grade_result=None,
        guide_text=None,
    )

    await get_inquiry_automation_graph().ainvoke(state)

    logger.info(
        "inquiry_automation_completed",
        user_chat_id=automation_input.user_chat_id,
    )
