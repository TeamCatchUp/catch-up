from __future__ import annotations

from dataclasses import dataclass

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import SyncAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.db.models import SyncConnector
from catchup.events.enums import EventType


@dataclass(slots=True, frozen=True)
class SyncAuditContext:
    connector: SyncConnector
    scope_id: str
    target_id: str | None = None
    job_id: str | None = None
    task_id: str | None = None


def emit_sync_trigger_audit(
    *,
    action: str,
    status: AuditEventStatus,
    audit_context: SyncAuditContext,
    context: str | None = None,
    level: AuditLevel = AuditLevel.INFO,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=action,
        event_status=status,
        level=level,
        metadata=SyncAuditMetadata(
            context=context,
            connector=audit_context.connector,
            scope_id=audit_context.scope_id,
            target_id=audit_context.target_id,
            job_id=audit_context.job_id,
        ),
    )


def emit_sync_ingestion_audit(
    *,
    action: str,
    status: AuditEventStatus,
    audit_context: SyncAuditContext,
    context: str | None = None,
    token_usage: int | None = None,
    level: AuditLevel = AuditLevel.INFO,
) -> None:
    emit_audit_event(
        event_type=EventType.SYNC,
        event_action=action,
        event_status=status,
        level=level,
        metadata=SyncAuditMetadata(
            context=context,
            connector=audit_context.connector,
            scope_id=audit_context.scope_id,
            target_id=audit_context.target_id,
            job_id=audit_context.job_id,
            task_id=audit_context.task_id,
            token_usage=token_usage,
        ),
    )
