"""
[DEPRECATED WARNING] BaseAuditAction 기반 감사로그 작성 방식 개편
"""
import structlog

from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import BaseAuditMetadata
from catchup.events.bus import bus
from catchup.events.enums import EventTopic
from catchup.observability.logging.context import get_request_context

logger = structlog.get_logger()

# [DEPRECATED WARNING]
def emit_audit_event(
    event_status: AuditEventStatus,
    level: AuditLevel = AuditLevel.INFO,
    event_type: str | None = None,  # TODO: BaseAuditAction이 안정화 된 이후 제거
    event_action: str | None = None,  # TODO: BaseAuditAction이 안정화 된 이후 제거
    metadata: BaseAuditMetadata | None = None,
    immediate: bool = True,  # TODO: 삭제
    **extra_payload
):
    """
    (Deprecated) Audit 전용 인터페이스 이벤트 Emitter
    """
    
    try:
        context = get_request_context()

        extra_payload.setdefault("actor", context.get("actor"))
        extra_payload.setdefault("trace_id", context.get("trace_id"))

        bus.emit(
            topic=EventTopic.AUDIT,
            immediate=True,  # 감사 로그 이벤트는 언제나 즉시 실행
            event_type=event_type,
            event_action=event_action,
            event_status=event_status,
            level=level,
            metadata=metadata,
            **extra_payload
        )
    except Exception as e:
        logger.warning(
            "audit_event_emit_failed",
            event_type=event_type,
            event_action=event_action,
            error=str(e),
            exc_info=True,
        )
