from __future__ import annotations

from typing import Any

from catchup.audit.base import (
    AuditLevel,
    build_actor,
    emit_audit_event,
    resolve_audit_level,
)
from catchup.audit.enums import ChatEventAction, EventType

def message_sent(
    *,
    session_id: str,
    query_type: str,
    rag_pipeline: str | None = None,
    llm: str | None = None,
    connectors_searched: list[str] | None = None,
    citations_count: int | None = None,
    duration_ms: int | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.CHAT,
        event_action=ChatEventAction.MESSAGE_SENT,
        actor=build_actor(actor=actor),
        metadata={
            "session_id": session_id,
            "query_type": query_type,
            "rag_pipeline": rag_pipeline,
            "llm": llm,
            "connectors_searched": connectors_searched,
            "citations_count": citations_count,
            "duration_ms": duration_ms,
            "result": "success",
        },
        level=level or "info",
    )


def message_failed(
    *,
    session_id: str,
    query_type: str,
    failure_reason: str | None = None,
    latency_ms: int | None = None,
    rag_pipeline: str | None = None,
    llm: str | None = None,
    connectors_searched: list[str] | None = None,
    actor: dict[str, Any] | None = None,
    result: str = "failure",
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.CHAT,
        event_action=ChatEventAction.MESSAGE_FAILED,
        actor=build_actor(actor=actor),
        metadata={
            "session_id": session_id,
            "query_type": query_type,
            "failure_reason": failure_reason,
            "latency_ms": latency_ms,
            "rag_pipeline": rag_pipeline,
            "llm": llm,
            "connectors_searched": connectors_searched,
            "result": result,
        },
        level=resolve_audit_level(result, level),
    )
