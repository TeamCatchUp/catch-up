from sqlalchemy.orm import Session

from catchup.db.models import UserPromptSetting
from catchup.server.settings.schemas import PromptUpdateRequest


def get_user_prompt_settings(
    db: Session,
    user_id: int,
) -> UserPromptSetting | None:
    return db.query(UserPromptSetting).filter_by(user_id=user_id).first()


def upsert_user_prompt_settings(
    db: Session,
    user_id: int,
    payload: PromptUpdateRequest,
) -> UserPromptSetting:
    settings = get_user_prompt_settings(
        db=db,
        user_id=user_id,
    )
    if settings is None:
        settings = UserPromptSetting(user_id=user_id)
        db.add(settings)
        
    settings.job_role = payload.job_role
    settings.custom_job_text = payload.custom_job_text
    settings.job_description = payload.job_description
    settings.selected_options = payload.selected_options
    settings.custom_prompt = payload.custom_prompt
    
    return settings