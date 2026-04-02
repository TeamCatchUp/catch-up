from typing import Any

import structlog

from catchup.audit.actions import UnknownTaskAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.base import BaseAuditAction
from catchup.audit.metadata import BaseAuditMetadata
from catchup.audit.schemas import AuditActor
from catchup.observability.logging import get_logger

logger = structlog.get_logger()

def audit_event_handler(**kwargs: Any) -> None:
    """
    EventBus로부터 감사로그 발행 이벤트를 전달받아 데이터를 정제하고 
    실제 structlog 기반 로그를 남기는 핸들러.
    """
    action: BaseAuditAction = kwargs.pop("action", UnknownTaskAction.UNKNOWN)
    status: AuditStatus = kwargs.pop("status", AuditStatus.UNKNOWN)
    level: AuditLevel = kwargs.pop("level", "info")
    
    # metadata 셋업
    metadata_obj = kwargs.pop("metadata", None)
    meta_payload = {}
    if metadata_obj and isinstance(metadata_obj, BaseAuditMetadata):
            meta_payload = metadata_obj.model_dump(exclude_none=True, mode="json")
    
    # actor 추출
    raw_actor = kwargs.pop("actor", None)
    actor_payload = None
    if raw_actor:
        actor = AuditActor.from_user_snapshot(raw_actor)
        actor_payload = actor.model_dump(exclude_none=True) if actor else None
 
    # 로그 출력
    audit_logger = get_logger("catchup.audit")
    log_method = getattr(audit_logger, level, audit_logger.info)
    log_method(
        event=action.full,
        status=status,
        actor=actor_payload,
        metadata=meta_payload
    )
