from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import BaseAuditMetadata
from catchup.events.enums import EventTopic
from catchup.events.bus import bus
from catchup.observability.logging.context import get_request_context


def emit_audit_event(
    event_type: str, 
    event_action: str, 
    level: AuditLevel = AuditLevel.INFO,
    metadata: BaseAuditMetadata | None = None,
    **extra_payload
):
    """Audit 전용 인터페이스 이벤트 Emitter"""
    
    context = get_request_context()
    
    extra_payload.setdefault("actor", context.get("actor"))
    extra_payload.setdefault("trace_id", context.get("trace_id"))
    
    bus.emit(
        topic=EventTopic.AUDIT,
        event_type=event_type,
        event_action=event_action,
        level=level,
        metadata=metadata,
        **extra_payload
    )