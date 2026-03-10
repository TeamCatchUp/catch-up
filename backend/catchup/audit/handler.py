from catchup.audit.base import emit_audit_event
from catchup.audit.schemas import AuditActor


def audit_event_handler(**kwargs):
    
    raw_actor = kwargs.get("actor")    
    actor = AuditActor.from_dict(raw_actor)
         
    emit_audit_event(
        event_type=kwargs.get("event_type"),
        event_action=kwargs.get("event_action"),
        actor=actor.model_dump(),
        metadata=kwargs.get("metadata", {}),
        remote_addr=kwargs.get("remote_addr", {}),
        level=kwargs.get("level", "info")
    )