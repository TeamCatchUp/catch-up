from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from catchup.auth.schemas import UserCreate
from catchup.db.models import User, UserWorkspace, Workspace


def get_user_by_email(
    db: Session,
    email: str
) -> User | None:
    return db.execute(select(User).filter_by(email=email)).scalar_one_or_none()


def create_new_user(
    db: Session, 
    user_create: UserCreate
) -> User:
    new_user = User(**user_create.model_dump())

    db.add(new_user)
    
    return new_user


def update_user_refresh_token(
    db: Session,
    user_id: int,
    refresh_token: str | None
):
    stmt = update(User).where(User.id == user_id).values(refresh_token=refresh_token)
    
    db.execute(stmt)


def get_user_with_full_context(
    db: Session,
    user_id: int
) -> User | None:

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.workspace_links)
            .selectinload(UserWorkspace.workspace)
            .selectinload(Workspace.company)
        )
    )
    
    return db.scalars(stmt).one_or_none()