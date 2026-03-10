from catchup.audit.base import emit_audit_event
from catchup.audit.schemas import AuditActor


def audit_event_handler(**kwargs):
    
    raw_actor = kwargs.get("actor")    
    actor = AuditActor.from_user_snapshot(raw_actor)
    
    actor_payload = actor.model_dump(exclude_none=True) if actor else None
         
    emit_audit_event(
        event_type=kwargs.get("event_type"),
        event_action=kwargs.get("event_action"),
        actor=actor_payload,
        metadata=kwargs.get("metadata", {}),
        remote_addr=kwargs.get("remote_addr", {}),
        level=kwargs.get("level", "info")
    )