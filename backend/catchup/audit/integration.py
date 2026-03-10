# Deprecated: Use emit_audit_event()

from __future__ import annotations

from typing import Any

from catchup.audit.base import (
    AuditLevel,
    build_actor,
    emit_audit_event,
    resolve_audit_level,
)
from catchup.audit.enums import EventType, IntegrationEventAction

def oauth_connect(
    *,
    user_id: int | str | None,
    email: str | None,
    connector: str,
    result: str,
    provider_account_id: str | None = None,
    tenant_id: str | None = None,
    scopes_granted: list[str] | None = None,
    connection_status: str | None = None,
    failure_reason: str | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.OAUTH_CONNECT,
        actor=build_actor(user_id=user_id, email=email, actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "provider_account_id": provider_account_id,
            "tenant_id": tenant_id,
            "scopes_granted": scopes_granted,
            "connection_status": connection_status,
            "failure_reason": failure_reason,
            "connector_details": connector_details or {},
        },
        level=resolve_audit_level(result, level),
    )

def oauth_disconnect(
    *,
    user_id: int | str | None,
    email: str | None,
    connector: str,
    result: str,
    provider_account_id: str | None = None,
    tenant_id: str | None = None,
    failure_reason: str | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.OAUTH_DISCONNECT,
        actor=build_actor(user_id=user_id, email=email, actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "provider_account_id": provider_account_id,
            "tenant_id": tenant_id,
            "failure_reason": failure_reason,
            "connector_details": connector_details or {},
        },
        level=resolve_audit_level(result, level),
    )


def oauth_refresh(
    *,
    user_id: int | str | None,
    email: str | None,
    connector: str,
    result: str,
    provider_account_id: str | None = None,
    tenant_id: str | None = None,
    token_expires_in_seconds: int | None = None,
    failure_reason: str | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.OAUTH_REFRESH,
        actor=build_actor(user_id=user_id, email=email, actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "provider_account_id": provider_account_id,
            "tenant_id": tenant_id,
            "token_expires_in_seconds": token_expires_in_seconds,
            "failure_reason": failure_reason,
            "connector_details": connector_details or {},
        },
        level=resolve_audit_level(result, level),
    )


def webhook_register(
    *,
    user_id: int | str | None,
    email: str | None,
    connector: str,
    result: str,
    endpoint: str | None = None,
    subscribed_events: list[str] | None = None,
    failure_reason: str | None = None,
    connector_details: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
    level: AuditLevel | None = None,
) -> None:
    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.WEBHOOK_REGISTER,
        actor=build_actor(user_id=user_id, email=email, actor=actor),
        metadata={
            "connector": connector,
            "result": result,
            "endpoint": endpoint,
            "subscribed_events": subscribed_events,
            "failure_reason": failure_reason,
            "connector_details": connector_details or {},
        },
        level=resolve_audit_level(result, level),
    )
