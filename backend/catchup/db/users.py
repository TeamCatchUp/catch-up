from typing import Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from catchup.auth.schemas import UserCreate
from catchup.db.models import OAuthUser, User, UserWorkspace, Workspace


def get_user_by_email(
    db: Session,
    email: str
) -> User | None:
    return db.scalar(
        select(User)
        .filter_by(email=email)
    )


def get_user_by_sub(
    db: Session,
    sub: str
) -> User | None:
    return db.scalar(
        select(User)
        .join(OAuthUser)
        .where(OAuthUser.sub == sub)
    )


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
    return db.scalar(stmt)


def get_oauth_user_with_sub(
    db: Session,
    sub: str
) -> Optional[OAuthUser]:
    
    stmt = (
        select(OAuthUser)
        .where(OAuthUser.sub == sub)
    )
    
    return db.scalar(stmt)


def get_all_oauth_users(
    db: Session
) -> list[OAuthUser] :
    """어드민용: 전체 OAuth 유저 목록 조회"""
    return db.scalars(select(OAuthUser)).all()


def get_all_users_for_admin(
    db: Session,
    skip: int = 0,
    limit: int = 50
) -> tuple[list[User], int]:
    """어드민용: 전체 Catch Up 유저 목록 조회"""
    
    total_count = db.scalar(
        select(func.count())
        .select_from(User)
    ) or 0    
    
    stmt = (
        select(User)
        .order_by(User.name.asc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count