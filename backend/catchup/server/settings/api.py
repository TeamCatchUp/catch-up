import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.audit.actions import UserCustomPromptAction
from catchup.audit.contexts import AuditContext
from catchup.audit.utils import audit_log
from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.models import UserPromptSetting
from catchup.db.user_prompt_settings import get_user_prompt_settings
from catchup.db.user_prompt_settings import upsert_user_prompt_settings
from catchup.server.settings.schemas import PromptSettingsRequest
from catchup.server.settings.schemas import PromptSettingsResponse

logger = structlog.get_logger()


router = APIRouter(
    prefix="/api/v1/settings",
    tags=["settings"]
)


@router.get(
    path="/prompts",
    response_model=PromptSettingsResponse,
    description="사용자 맞춤형 프롬프트 조회"
)
def get_custom_prompt(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    settings = get_user_prompt_settings(
        db=db,
        user_id=current_user.id
    )
    if settings is None:
        return PromptSettingsResponse()
    return PromptSettingsResponse.model_validate(settings)


def _resolve_custom_prompt_action(
    settings: UserPromptSetting | None,
    payload: PromptSettingsRequest,
) -> UserCustomPromptAction:
    if settings is None:
        return UserCustomPromptAction.CREATE
    if payload.custom_prompt is None:
        return UserCustomPromptAction.DELETE
    return UserCustomPromptAction.EDIT


@router.patch(
    path="/prompts",
    response_model=PromptSettingsResponse,
    description="사용자 맞춤형 프롬프트 수정"
)
@audit_log()
def update_custom_prompt(
    payload: PromptSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    settings = get_user_prompt_settings(
        db=db, 
        user_id=current_user.id
    )
    
    AuditContext.get().action = _resolve_custom_prompt_action(
        settings=settings,
        payload=payload,
    )
    
    try:
        settings = upsert_user_prompt_settings(
            db=db,
            user_id=current_user.id,
            job_role=payload.job_role,
            custom_job_text=payload.custom_job_text,
            job_description=payload.job_description,
            selected_options=payload.selected_options,
            custom_prompt=payload.custom_prompt,
        )
        db.commit()
        logger.info(
            "user_prompt_settings_update",
            status="success"
        )
    except Exception as e:
        db.rollback()
        logger.error(
            "user_prompt_settings_update",
            status="failed",
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="맞춤형 프롬프트 설정 업데이트 실패"
        )
    
    return PromptSettingsResponse.model_validate(settings)
