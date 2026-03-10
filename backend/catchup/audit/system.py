# Deprecated: Use emit_audit_event()

from __future__ import annotations

from typing import Any

from catchup.audit.base import (
    AuditLevel,
    build_actor,
    emit_audit_event,
    resolve_audit_level,
)
from catchup.audit.enums import EventType, SystemEventAction


def system_event(
    *,
    action: SystemEventAction,
    result: str = "success",
    metadata: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    payload = {"result": result}
    if metadata:
        payload.update(metadata)

    emit_audit_event(
        event_type=EventType.SYSTEM,
        event_action=action,
        actor=build_actor(actor=actor),
        metadata=payload,
        level=resolve_audit_level(result, level),
    )
