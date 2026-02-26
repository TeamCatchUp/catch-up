from __future__ import annotations

from typing import Any

from catchup.audit.base import (
    AuditLevel,
    build_actor,
    emit_audit_event,
    resolve_audit_level,
)
from catchup.audit.enums import AuthEventAction, EventType

def login_attempt(
    *,
    email: str | None,
    provider: str,
    result: str,
    failure_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    token_issued: bool | None = None,
    is_new_user: bool | None = None,
    user_status: str | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.AUTH,
        event_action=AuthEventAction.LOGIN_ATTEMPT,
        actor=build_actor(actor=actor),
        metadata={
            "email": email,
            "provider": provider,
            "result": result,
            "failure_reason": failure_reason,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "token_issued": token_issued,
            "is_new_user": is_new_user,
            "user_status": user_status,
        },
        level=resolve_audit_level(result, level),
    )

def token_refresh(
    *,
    user_id: int | str | None,
    email: str | None,
    result: str,
    failure_reason: str | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.AUTH,
        event_action=AuthEventAction.TOKEN_REFRESH,
        actor=build_actor(
            user_id=user_id,
            email=email,
            actor=actor,
        ),
        metadata={
            "result": result,
            "failure_reason": failure_reason,
        },
        level=resolve_audit_level(result, level),
    )


def logout(
    *,
    user_id: int | str | None,
    email: str | None,
    result: str = "success",
    failure_reason: str | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.AUTH,
        event_action=AuthEventAction.LOGOUT,
        actor=build_actor(
            user_id=user_id,
            email=email,
            actor=actor,
        ),
        metadata={
            "result": result,
            "failure_reason": failure_reason,
        },
        level=resolve_audit_level(result, level),
    )