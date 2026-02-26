"""
Slack 엔티티 CRUD 함수

SlackWorkspace, SlackChannel, SlackUser 테이블에 대한 CRUD 작업 수행.
정적 데이터를 RDBMS에 저장하고 조회.
"""

from datetime import datetime, timezone

from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from catchup.connectors.slack.schemas import (
    SlackChannel as SlackChannelSchema,
    SlackUserProfile as SlackUserProfileSchema,
    SlackWorkspace as SlackWorkspaceSchema,
)
from catchup.db.models import SlackChannelMember, SlackWorkspace, SlackChannel, SlackChannelType, SlackUser


# ============================================================
# Workspace CRUD
# ============================================================

def upsert_workspace(db: Session, workspace: SlackWorkspaceSchema) -> SlackWorkspace:
    """
    워크스페이스 Upsert (Insert or Update)

    Args:
        db: SQLAlchemy 세션
        workspace: SlackWorkspace Pydantic 스키마
    """
    stmt = insert(SlackWorkspace).values(
        id=workspace.id,
        name=workspace.name,
        domain=workspace.domain,
        url=workspace.url,
        email_domain=workspace.email_domain,
        icon_url=workspace.icon_url,
        enterprise_id=workspace.enterprise_id,
        enterprise_name=workspace.enterprise_name,
        synced_at=datetime.now(timezone.utc),
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": workspace.name,
            "domain": workspace.domain,
            "url": workspace.url,
            "email_domain": workspace.email_domain,
            "icon_url": workspace.icon_url,
            "enterprise_id": workspace.enterprise_id,
            "enterprise_name": workspace.enterprise_name,
            "synced_at": datetime.now(timezone.utc),
        }
    )
    db.execute(stmt)
    db.commit()

    return get_workspace(db, workspace.id)


def get_workspace(db: Session, workspace_id: str) -> SlackWorkspace | None:
    """워크스페이스 조회"""
    stmt = select(SlackWorkspace).where(SlackWorkspace.id == workspace_id)
    return db.execute(stmt).scalar_one_or_none()


def delete_workspace(db: Session, workspace_id: str) -> int:
    """워크스페이스 삭제"""
    stmt = delete(SlackWorkspace).where(SlackWorkspace.id == workspace_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


# ============================================================
# Channel CRUD
# ============================================================

def upsert_channels_bulk(
    db: Session,
    team_id: str,
    channels: list[SlackChannelSchema],
) -> int:
    """
    채널 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        team_id: Slack 워크스페이스 ID
        channels: SlackChannel Pydantic 스키마 리스트

    Returns:
        처리된 채널 수
    """
    if not channels:
        return 0

    now = datetime.now(timezone.utc)
    channels_data = [
        {
            "id": ch.id,
            "team_id": team_id,
            "name": ch.name,
            "channel_type": SlackChannelType(ch.channel_type),
            "topic": ch.topic,
            "purpose": ch.purpose,
            "creator_id": ch.creator_id,
            "member_count": ch.member_count,
            "is_archived": ch.is_archived,
            "is_private": ch.is_private,
            "created_at": ch.created_at or now,
            "synced_at": now,
        }
        for ch in channels
    ]

    stmt = insert(SlackChannel).values(channels_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": stmt.excluded.name,
            "channel_type": stmt.excluded.channel_type,
            "topic": stmt.excluded.topic,
            "purpose": stmt.excluded.purpose,
            "member_count": stmt.excluded.member_count,
            "is_archived": stmt.excluded.is_archived,
            "is_private": stmt.excluded.is_private,
            "synced_at": stmt.excluded.synced_at,
        }
    )
    db.execute(stmt)
    db.commit()

    return len(channels)


def get_channel(db: Session, channel_id: str) -> SlackChannel | None:
    """채널 조회"""
    stmt = select(SlackChannel).where(SlackChannel.id == channel_id)
    return db.execute(stmt).scalar_one_or_none()


def get_channels_by_team(db: Session, team_id: str) -> list[SlackChannel]:
    """팀의 모든 채널 조회"""
    stmt = (
        select(SlackChannel)
        .where(SlackChannel.team_id == team_id)
        .order_by(SlackChannel.name)
    )
    return list(db.execute(stmt).scalars().all())


def delete_channel(db: Session, channel_id: str) -> int:
    """채널 삭제"""
    stmt = delete(SlackChannel).where(SlackChannel.id == channel_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def delete_channels_by_team(db: Session, team_id: str) -> int:
    """팀의 모든 채널 삭제"""
    stmt = delete(SlackChannel).where(SlackChannel.team_id == team_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

def upsert_channel_from_event(
        db: Session,
        team_id: str,
        channel_id: str,
        name: str,
        is_private: bool = False,
        creator_id: str | None = None,
) -> None:
    """
    Webhook Channel Event으로 단일 채널 Upsert
    """
    now = datetime.now(timezone.utc)
    channel_type = SlackChannelType.PRIVATE if is_private else SlackChannelType.PUBLIC

    stmt = insert(SlackChannel).values(
        id=channel_id,
        team_id=team_id,
        name=name,
        channel_type=channel_type,
        creator_id=creator_id,
        is_private=is_private,
        created_at=now,
        synced_at=now,
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": name,
            "is_private": is_private,
            "synced_at":now
        }
    )
    db.execute(stmt)
    db.commit()

def update_channel_archive(db:Session, channel_id:str, is_archived: bool)->None:
    """채널 Archive 상태 업데이트"""
    stmt = (
        update(SlackChannel)
        .where(SlackChannel.id == channel_id)
        .values(is_archived=is_archived, synced_at=datetime.now(timezone.utc))
    )
    db.execute(stmt)
    db.commit()

# ============================================================
# User CRUD
# ============================================================

def upsert_users_bulk(
    db: Session,
    team_id: str,
    users: list[SlackUserProfileSchema],
) -> int:
    """
    사용자 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        team_id: Slack 워크스페이스 ID
        users: SlackUserProfile Pydantic 스키마 리스트

    Returns:
        처리된 사용자 수
    """
    if not users:
        return 0

    now = datetime.now(timezone.utc)
    users_data = [
        {
            "team_id": team_id,
            "user_id": u.id,
            "name": u.name,
            "real_name": u.real_name or u.name,
            "display_name": u.display_name or u.name,
            "deleted": u.deleted,
            "email": u.email,
            "avatar_url": u.avatar_url,
            "title": u.title,
            "phone": u.phone,
            "tz": u.tz,
            "tz_label": u.tz_label,
            "is_bot": u.is_bot,
            "is_admin": u.is_admin,
            "is_owner": u.is_owner,
            "is_restricted": u.is_restricted,
            "updated_at": u.updated_at,
            "synced_at": now,
        }
        for u in users
    ]

    stmt = insert(SlackUser).values(users_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["team_id", "user_id"],
        set_={
            "name": stmt.excluded.name,
            "real_name": stmt.excluded.real_name,
            "display_name": stmt.excluded.display_name,
            "deleted": stmt.excluded.deleted,
            "email": stmt.excluded.email,
            "avatar_url": stmt.excluded.avatar_url,
            "title": stmt.excluded.title,
            "phone": stmt.excluded.phone,
            "tz": stmt.excluded.tz,
            "tz_label": stmt.excluded.tz_label,
            "is_bot": stmt.excluded.is_bot,
            "is_admin": stmt.excluded.is_admin,
            "is_owner": stmt.excluded.is_owner,
            "is_restricted": stmt.excluded.is_restricted,
            "updated_at": stmt.excluded.updated_at,
            "synced_at": stmt.excluded.synced_at,
        }
    )
    db.execute(stmt)
    db.commit()

    return len(users)


def get_user(db: Session, team_id: str, user_id: str) -> SlackUser | None:
    """사용자 조회"""
    stmt = select(SlackUser).where(
        SlackUser.team_id == team_id,
        SlackUser.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_users_by_team(db: Session, team_id: str, include_deleted: bool = False) -> list[SlackUser]:
    """팀의 모든 사용자 조회"""
    stmt = select(SlackUser).where(SlackUser.team_id == team_id)
    if not include_deleted:
        stmt = stmt.where(SlackUser.deleted == False)
    stmt = stmt.order_by(SlackUser.name)
    return list(db.execute(stmt).scalars().all())


def get_users_by_ids(
    db: Session,
    team_id: str,
    user_ids: list[str],
) -> dict[str, SlackUser]:
    """
    특정 user_id 목록으로 사용자 조회

    Returns:
        user_id → SlackUser 매핑 딕셔너리
    """
    if not user_ids:
        return {}

    stmt = select(SlackUser).where(
        SlackUser.team_id == team_id,
        SlackUser.user_id.in_(user_ids),
    )
    users = db.execute(stmt).scalars().all()
    return {user.user_id: user for user in users}


def delete_user(db: Session, team_id: str, user_id: str) -> int:
    """사용자 삭제"""
    stmt = delete(SlackUser).where(
        SlackUser.team_id == team_id,
        SlackUser.user_id == user_id,
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def delete_users_by_team(db: Session, team_id: str) -> int:
    """팀의 모든 사용자 삭제"""
    stmt = delete(SlackUser).where(SlackUser.team_id == team_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

# ============================================================
# Channel Member CRUD
# ============================================================
def replace_channel_members(
    db: Session,
    team_id: str,
    channel_id: str,
    user_ids: list[str],
) -> int:
    db.execute(
        delete(SlackChannelMember).where(
            SlackChannelMember.team_id == team_id,
            SlackChannelMember.channel_id == channel_id,
        )
    )

    if not user_ids:
        db.commit()
        return 0
    
    now = datetime.now(timezone.utc)
    members_data = [
        {
            "team_id": team_id,
            "channel_id": channel_id, 
            "user_id": uid,
            "synced_at": now,
        }
        for uid in user_ids
    ]

    db.execute(insert(SlackChannelMember).values(members_data))
    db.commit()
    
    return len(user_ids)

def delete_channel_members_by_team(db:Session, team_id:str) -> int:
    stmt = delete(SlackChannelMember).where(SlackChannelMember.team_id == team_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

def add_channel_member(db:Session, team_id:str, channel_id:str, user_id:str)->None:
    stmt = insert(SlackChannelMember).values(
        team_id=team_id,
        channel_id=channel_id,
        user_id=user_id,
        synced_at=datetime.now(timezone.utc),
    ).on_conflict_do_nothing()
    db.execute(stmt)
    db.commit()

def remove_channel_member(db:Session, team_id:str, channel_id:str, user_id:str)->None:
    stmt = delete(SlackChannelMember).where(
        SlackChannelMember.team_id == team_id,
        SlackChannelMember.channel_id == channel_id,
        SlackChannelMember.user_id == user_id,
    )
    db.execute(stmt)
    db.commit()
