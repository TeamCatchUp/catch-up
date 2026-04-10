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
    fields: dict,
) -> UserPromptSetting:
    settings = get_user_prompt_settings(db=db, user_id=user_id)
    if settings is None:
        settings = UserPromptSetting(user_id=user_id)
        db.add(settings)

    for field, value in fields.items():
        setattr(settings, field, value)

    return settings
