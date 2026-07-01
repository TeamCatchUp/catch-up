from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import HumanMessage
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler

from catchup.automations.graph import get_inquiry_automation_graph
from catchup.automations.state import AutomationState
from catchup.db.models import SourceType
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.langfuse.configs import get_observe
from catchup.schemas.context import GlobalContext

logger = structlog.get_logger(__name__)
observe = get_observe()


@dataclass(frozen=True)
class AutomationInput:
    inquiry_text: str
    user_chat_id: str
    slack_channel_id: str
    slack_credential_id: int
    global_context: GlobalContext
    guide_instruction: str | None = None
    quiet_period_seconds: int | None = None


def _build_invoke_config(client: Any) -> dict[str, Any]:
    """Langfuse CallbackHandler를 주입한 invoke config를 반환한다."""
    try:
        trace_id = client.get_current_trace_id()
        return {"callbacks": [CallbackHandler(trace_context={"trace_id": trace_id})]}
    except Exception as exc:
        logger.warning("langfuse_invoke_config_failed", error=str(exc))
        return {}


def _build_trace_context(automation_input: AutomationInput) -> Any:
    """트레이스 레벨 태그/메타데이터를 전파하는 컨텍스트 매니저를 반환한다."""
    try:
        return propagate_attributes(
            session_id=automation_input.user_chat_id,
            tags=["inquiry-automation"],
            metadata={
                "workspace_id": str(automation_input.global_context.workspace.id),
                "slack_channel_id": automation_input.slack_channel_id,
            },
        )
    except Exception as exc:
        logger.warning("langfuse_trace_context_failed", error=str(exc))
        return nullcontext()


@observe(name="inquiry-automation")
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

    client = get_langfuse_client()
    invoke_config = _build_invoke_config(client) if client is not None else {}
    trace_context = (
        _build_trace_context(automation_input)
        if client is not None
        else nullcontext()
    )

    with trace_context:
        result = await get_inquiry_automation_graph().ainvoke(
            state, config=invoke_config
        )

    if client is not None:
        try:
            client.update_current_span(
                input={"inquiry_text": automation_input.inquiry_text},
                output={"guide_text": (result or {}).get("guide_text")},
            )
        except Exception as exc:
            logger.warning("langfuse_update_span_failed", error=str(exc))

    logger.info(
        "inquiry_automation_completed",
        user_chat_id=automation_input.user_chat_id,
    )

    if client is not None:
        try:
            await run_in_threadpool(client.flush)
        except Exception as exc:
            logger.warning("langfuse_flush_failed", error=str(exc))
