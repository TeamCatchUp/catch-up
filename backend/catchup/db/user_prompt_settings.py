from sqlalchemy.orm import Session

from catchup.db.models import UserPromptSetting


def get_user_prompt_settings(
    db: Session,
    user_id: int,
) -> UserPromptSetting | None:
    return db.query(UserPromptSetting).filter_by(user_id=user_id).first()


def upsert_user_prompt_settings(
    db: Session,
    user_id: int,
    job_role: str | None,
    custom_job_text: str | None,
    job_description: str | None,
    selected_options: list,
    custom_prompt: str | None,
) -> UserPromptSetting:
    settings = get_user_prompt_settings(db=db, user_id=user_id)
    if settings is None:
        settings = UserPromptSetting(user_id=user_id)
        db.add(settings)

    settings.job_role = job_role
    settings.custom_job_text = custom_job_text
    settings.job_description = job_description
    settings.selected_options = selected_options
    settings.custom_prompt = custom_prompt

    return settings