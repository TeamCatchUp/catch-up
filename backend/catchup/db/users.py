from sqlalchemy import select, update
from sqlalchemy.orm import Session

from catchup.auth.schemas import UserCreate
from catchup.db.models import User


def get_user_by_email(db: Session, email: str) -> User:
    return db.execute(select(User).filter_by(email=email)).scalar_one_or_none()


def create_new_user(db: Session, user_create: UserCreate) -> User:
    new_user = User(**user_create.model_dump())

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
        return new_user

    except Exception:
        db.rollback()
        raise


def update_user_refresh_token(db: Session, user_id: int, refresh_token: str | None):
    stmt = update(User).where(User.id == user_id).values(refresh_token=refresh_token)
    db.execute(stmt)
    db.commit()
