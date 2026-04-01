import structlog

from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.base import BaseAuditAction
from catchup.audit.metadata import BaseAuditMetadata
from catchup.events.bus import bus
from catchup.events.enums import EventTopic
from catchup.observability.logging.context import get_request_context

logger = structlog.get_logger()


def emit_audit_event(
    status: AuditStatus,
    level: AuditLevel = AuditLevel.INFO,
    action: BaseAuditAction | None = None,
    metadata: BaseAuditMetadata | None = None,
    **extra_payload
):
    """
    Audit 전용 인터페이스 이벤트 Emitter
    """
    
    try:
        context = get_request_context()

        extra_payload.setdefault("actor", context.get("actor"))
        extra_payload.setdefault("trace_id", context.get("trace_id"))
        
        bus.emit(
            topic=EventTopic.AUDIT,
            immediate=True,  # 감사 로그 이벤트는 즉시 발행
            action=action,
            status=status,
            level=level,
            metadata=metadata,
            **extra_payload
        )
    except Exception as e:
        logger.warning(
            "audit_event_emit_failed",
            action=action.full,
            error=str(e),
            exc_info=True,
        )
