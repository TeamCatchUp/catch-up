from typing import Any
from catchup.audit.schemas import AuditActor
from catchup.observability.logging import get_logger


def audit_event_handler(**kwargs: Any) -> None:
    """
    EventBus로부터 이벤트를 전달받아 데이터를 정제하고 
    실제 structlog로 로그를 남기는 최종 핸들러
    """
    event_type = kwargs.get("event_type")
    event_action = kwargs.get("event_action")
    level = str(kwargs.get("level", "info")).lower()
    metadata = kwargs.get("metadata")
    remote_addr = kwargs.get("remote_addr")
    trace_id = kwargs.get("trace_id")

    raw_actor = kwargs.get("actor")
    actor_payload = None
    if raw_actor:
        actor = AuditActor.from_user_snapshot(raw_actor)
        actor_payload = actor.model_dump(exclude_none=True) if actor else None

    payload: dict[str, Any] = {
        "event_type": str(event_type) if event_type else "unknown",
        "event_action": str(event_action) if event_action else "unknown",
    }

    if actor_payload:
        payload["actor"] = actor_payload
    if metadata:
        payload["metadata"] = metadata
    if remote_addr:
        payload["remote_addr"] = remote_addr
    if trace_id:
        payload["trace_id"] = trace_id

    audit_logger = get_logger("catchup.audit")
    log_method = getattr(audit_logger, level, audit_logger.info)
    log_method(str(event_action), **payload)