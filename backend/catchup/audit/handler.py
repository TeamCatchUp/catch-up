from catchup.audit.base import emit_audit_event
from catchup.audit.schemas import AuditActor
from catchup.db.models import OAuthUser, User


def audit_event_handler(**kwargs):
    
    actor = kwargs.get("actor")
    if actor:
        actor = AuditActor.from_dict(actor)
 
    emit_audit_event(
        event_type=kwargs.get("event_type"),
        event_action=kwargs.get("event_action"),
        actor=actor.model_dump(),
        metadata=kwargs.get("metadata", {}),
        level=kwargs.get("level", "info")
    )