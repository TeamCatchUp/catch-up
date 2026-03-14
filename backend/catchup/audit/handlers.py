from typing import Any

import structlog
from catchup.audit.metadata import BaseAuditMetadata
from catchup.audit.schemas import AuditActor
from catchup.observability.logging import get_logger


logger = structlog.get_logger()

def audit_event_handler(**kwargs: Any) -> None:
    """
    EventBus로부터 이벤트를 전달받아 데이터를 정제하고 
    실제 structlog로 로그를 남기는 최종 핸들러
    """
    event_action = kwargs.pop("event_action", "unknown")
    event_type = kwargs.pop("event_type", "unknown")
    event_status = kwargs.pop("event_status", "unknown")
    
    level = str(kwargs.pop("level", "info")).lower()
    
    metadata_obj = kwargs.pop("metadata", None)
    meta_payload = {}
    
    if metadata_obj and isinstance(metadata_obj, BaseAuditMetadata):
            meta_payload = metadata_obj.model_dump(exclude_none=True, mode="json")
    
    raw_actor = kwargs.pop("actor", None)
    actor_payload = None
    if raw_actor:
        actor = AuditActor.from_user_snapshot(raw_actor)
        actor_payload = actor.model_dump(exclude_none=True) if actor else None
 
    audit_logger = get_logger("catchup.audit")
    log_method = getattr(audit_logger, level, audit_logger.info)
        
    log_method(
        str(event_action),
        event_type=str(event_type),
        event_status=str(event_status),
        actor=actor_payload,
        metadata=meta_payload
    )