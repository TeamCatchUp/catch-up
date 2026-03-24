from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import structlog

from catchup.audit.enums import AuditEventStatus
from catchup.audit.service import emit_audit_event
from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.events.enums import EventType, UserCustomPromptEventAction

logger = structlog.get_logger()


router = APIRouter(
    prefix="/api/v1/settings",
    tags=["settings"]
)

class PromptUpdate(BaseModel):
    custom_prompt: str | None

@router.get(
    path="/prompts",
    description="사용자 맞춤형 프롬프트 조회"
)
def get_custom_prompt(
    current_user: User = Depends(get_current_user)
):
    logger.info("user_custom_prompt_read")
    return {"custom_prompt": current_user.custom_prompt}


@router.patch(
    path="/prompts",
    description="사용자 맞춤형 프롬프트 수정"
)
def update_custom_prompt(
    payload: PromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prompt = current_user.custom_prompt
    
    audit_event_type = EventType.USER_SETTINGS
    audit_event_action = None
    if prompt is None:
        audit_event_action = UserCustomPromptEventAction.CREATED
    else:
        if payload.custom_prompt is None:
            audit_event_action = UserCustomPromptEventAction.DELETED
        else:
            audit_event_action = UserCustomPromptEventAction.EDITED
    try:
        current_user.custom_prompt = payload.custom_prompt
        db.commit()  # Dirty check
        
        logger.info(
            "user_custom_prompt_update",
            status="success"
        )
        emit_audit_event(
            event_type=audit_event_type,
            event_action=audit_event_action,
            event_status=AuditEventStatus.SUCCESS
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "user_custom_prompt_update",
            status="failed",
            error=str(e)
        )
        emit_audit_event(
            event_type=audit_event_type,
            event_action=audit_event_action,
            event_status=AuditEventStatus.FAIL
        )
        raise HTTPException(
            status_code=500,
            detail="custom_prompt 업데이트 실패"
        )
    
    return {"custom_prompt": current_user.custom_prompt}
