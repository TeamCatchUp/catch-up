from typing import Optional
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from catchup.db.models import OAuthUser, User, UserRole, UserWorkspace, Workspace

def get_user_by_id(
    db: Session,
    user_id: int
) -> User | None:
    return db.scalar(
        select(User).where(User.id == user_id)
    )

def get_user_by_id_for_update(
    db: Session,
    user_id: int,
) -> User | None:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    return db.scalar(stmt)

def update_user_role(
    db: Session,
    *,
    user: User,
    role: UserRole,
) -> User:
    user.role = role
    db.flush()

    return user

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


def update_user_refresh_token(
    db: Session,
    user_id: int,
    refresh_token: str | None
) -> bool:
    stmt = update(User).where(User.id == user_id).values(refresh_token=refresh_token)
    result = db.execute(stmt)
    
    return result.rowcount > 0


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
    """전체 OAuth 유저 목록 조회"""
    return db.scalars(select(OAuthUser)).all()


def get_all_oauth_users_for_admin(
    db: Session,
    skip: int = 0,
    limit: int = 50,
) -> list[OAuthUser]:
    """어드민용: 전체 OAuth 유저 목록 조회 (페이지네이션)"""
    total_count = db.scalar(
        select(func.count())
        .select_from(OAuthUser)
    ) or 0
    
    stmt = (
        select(OAuthUser)
        .order_by(OAuthUser.name.asc())
        .offset(skip)
        .limit(limit)
    )
    
    items = db.scalars(stmt).all()
    
    return list(items), total_count


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