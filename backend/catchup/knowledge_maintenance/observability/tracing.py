"""
ChannelTalk UserChat 파이프라인을 위한 Langfuse Trace ID 계산 및 관측 유틸리티

UUID 5 기반의 결정론적 해시값으로 같은 UserChat에 대한 관측을 하나의 Trace으로 병합하고,
주어진 UUID를 통해 Langfuse CallbackHandler를 생성한다.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

TRACE_NAME = "channel_talk_user_chat_pipeline"

_TRACE_ID_NAMESPACE = uuid.UUID("d84c3d1e-4b3f-4c1a-9a4e-2f6f9c9a6b31")

_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def user_chat_trace_id(*, workspace_id: int, external_document_id: str) -> str:
    """
    같은 user_chat_id에 대해서 항상 같은 Trace_ID를 생성한다.
    """
    return uuid.uuid5(
        _TRACE_ID_NAMESPACE, f"{workspace_id}:{external_document_id}"
    ).hex


def is_valid_trace_id(trace_id: str) -> bool:
    """
    Langfuse가 받아들이는 trace id 형식인지 확인
    """
    return bool(_TRACE_ID_PATTERN.match(trace_id))


def llm_invoke_config(trace_id: str) -> dict[str, Any]:
    """
    주어진 trace_id를 LangChain LLM 호출에 연결하는 invoke config를 만든다.
    """
    if get_langfuse_client() is None:
        return {}
    if not is_valid_trace_id(trace_id):
        logger.warning("langfuse_invalid_trace_id", trace_id=trace_id)
        return {}
    try:
        from langfuse.langchain import CallbackHandler

        return {
            "callbacks": [
                CallbackHandler(trace_context={"trace_id": trace_id})
            ]
        }
    except Exception as error:
        logger.warning("langfuse_invoke_config_failed", error=str(error))
        return {}
