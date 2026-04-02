import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from catchup.audit.actions import UserCustomPromptAction
from catchup.audit.contexts import AuditContext
from catchup.audit.utils import audit_log
from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User

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


def _resolve_custom_prompt_action(
    prompt: str | None,
    payload: PromptUpdate,
) -> UserCustomPromptAction:
    if prompt is None:
        return UserCustomPromptAction.CREATE
    if payload.custom_prompt is None:
        return UserCustomPromptAction.DELETE
    return UserCustomPromptAction.EDIT


@router.patch(
    path="/prompts",
    description="사용자 맞춤형 프롬프트 수정"
)
@audit_log()
def update_custom_prompt(
    payload: PromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    AuditContext.get().action = _resolve_custom_prompt_action(
        prompt=current_user.custom_prompt,
        payload=payload,
    )
    
    try:
        current_user.custom_prompt = payload.custom_prompt
        db.commit()  # Dirty check
        
        logger.info(
            "user_custom_prompt_update",
            status="success"
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "user_custom_prompt_update",
            status="failed",
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="custom_prompt 업데이트 실패"
        )
    
    return {"custom_prompt": current_user.custom_prompt}
