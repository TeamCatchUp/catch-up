from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from catchup.audit.enums import AuditLevel, AuditResult, EventType
from catchup.observability.logging import get_logger

# TODO: 삭제
def build_actor(
    *,
    user_id: int | str | None = None,
    email: str | None = None,
    role: str | None = None,
    department: str | None = None,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if actor is not None:
        return actor
    
    if user_id is None and email is None and role is None and department is None:
        return None
    
    return {
        "user_id": user_id,
        "email": email,
        "role": role,
        "department": department,
    }


# TODO: 삭제
def resolve_audit_level(
    result: str,
    level: AuditLevel | None,
    *,
    failure_values: AuditResult | None = AuditResult.FAILURE,
    failure_level: AuditLevel = "warning",
    success_level: AuditLevel = "info",
) -> AuditLevel:
    if level is not None:
        return level
    return failure_level if result.lower() in failure_values else success_level


def emit_audit_event(
    *,
    event_type: EventType,
    event_action: StrEnum | str,
    actor: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    level: AuditLevel = "info",
    remote_addr: str | None = None,
) -> None:

    payload: dict[str, Any] = {
        "event_type": str(event_type),
        "event_action": str(event_action),
    }
    
    if remote_addr:
        payload["remote_addr"] = remote_addr

    if metadata:
        payload["metadata"] = metadata

    if actor:
        payload["actor"] = actor

    audit_logger = get_logger("catchup.audit")
    log_method = getattr(audit_logger, level)
    log_method(str(event_action), **payload)
