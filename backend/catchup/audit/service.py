from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import BaseAuditMetadata
from catchup.events.enums import EventTopic
from catchup.events.bus import bus
from catchup.observability.logging.context import get_request_context


def emit_audit_event(
    event_type: str,
    event_action: str,
    event_status: AuditEventStatus | None = None,
    level: AuditLevel = AuditLevel.INFO,
    metadata: BaseAuditMetadata | None = None,
    immediate: bool = False,
    **extra_payload
):
    """
    Audit 전용 인터페이스 이벤트 Emitter
    
    [IMPORTANT]
    감사 로그는 발생 시점의 정확성이 중요하므로 기본적으로 immediate=True를 사용한다.
    - True (Default): 이벤트 루프를 블로킹하지 않고 즉시 별도 스레드에서 실행 (to_thread).
    - False: FastAPI BackgroundTasks에 등록되어 응답 종료 후 실행됨.
    - event_status: ATTEMPT | SUCCESS | FAIL
    """

    context = get_request_context()

    extra_payload.setdefault("actor", context.get("actor"))
    extra_payload.setdefault("trace_id", context.get("trace_id"))

    if event_status is not None:
        extra_payload["event_status"] = event_status

    bus.emit(
        topic=EventTopic.AUDIT,
        immediate=immediate,
        event_type=event_type,
        event_action=event_action,
        level=level,
        metadata=metadata,
        **extra_payload
    )
