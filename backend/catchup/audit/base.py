from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any, Literal


from catchup.audit.enums import EventType
from catchup.observability.logging import get_logger

AuditLevel = Literal["debug", "info", "warning", "error", "critical"]
DEFAULT_FAILURE_VALUES = {
    "failure",
    "failed",
    "error",
    "partial_failure",
    "timeout",
}

audit_logger = get_logger("catchup.audit")

_LEVEL_TO_LOGGER_METHOD: dict[AuditLevel, Callable[..., Any]] = {
    "debug": audit_logger.debug,
    "info": audit_logger.info,
    "warning": audit_logger.warning,
    "error": audit_logger.error,
    "critical": audit_logger.critical,
}

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

def resolve_audit_level(
    result: str,
    level: AuditLevel | None,
    *,
    failure_values: set[str] = DEFAULT_FAILURE_VALUES,
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
) -> None:
    payload: dict[str, Any] = {
        "event_type": str(event_type),
        "event_action": str(event_action),
        "metadata": metadata or {},
    }

    if actor is not None:
        payload["actor"] = actor
    
    log_method = _LEVEL_TO_LOGGER_METHOD[level]
    log_method(str(event_action), **payload)
