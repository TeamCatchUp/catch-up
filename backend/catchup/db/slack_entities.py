"""
Slack 엔티티 CRUD 함수

SlackWorkspace, SlackChannel, SlackUser 테이블에 대한 CRUD 작업 수행.
정적 데이터를 RDBMS에 저장하고 조회.
"""

from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from catchup.db.models import SlackWorkspace, SlackChannel, SlackChannelType, SlackUser


# ============================================================
# Workspace CRUD
# ============================================================

def upsert_workspace(
    db: Session,
    workspace_id: str,
    name: str,
    domain: str,
    url: str,
    email_domain: str | None = None,
    icon_url: str | None = None,
    enterprise_id: str | None = None,
    enterprise_name: str | None = None,
) -> SlackWorkspace:
    """
    워크스페이스 Upsert (Insert or Update)
    """
    stmt = insert(SlackWorkspace).values(
        id=workspace_id,
        name=name,
        domain=domain,
        url=url,
        email_domain=email_domain,
        icon_url=icon_url,
        enterprise_id=enterprise_id,
        enterprise_name=enterprise_name,
        synced_at=datetime.now(timezone.utc),
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": name,
            "domain": domain,
            "url": url,
            "email_domain": email_domain,
            "icon_url": icon_url,
            "enterprise_id": enterprise_id,
            "enterprise_name": enterprise_name,
            "synced_at": datetime.now(timezone.utc),
        }
    )
    db.execute(stmt)
    db.commit()

    return get_workspace(db, workspace_id)


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

def upsert_channel(
    db: Session,
    channel_id: str,
    team_id: str,
    name: str,
    channel_type: SlackChannelType,
    topic: str | None = None,
    purpose: str | None = None,
    creator_id: str | None = None,
    member_count: int = 0,
    is_archived: bool = False,
    is_private: bool = False,
    created_at: datetime | None = None,
) -> SlackChannel:
    """
    채널 Upsert (Insert or Update)
    """
    now = datetime.now(timezone.utc)
    created_at = created_at or now

    stmt = insert(SlackChannel).values(
        id=channel_id,
        team_id=team_id,
        name=name,
        channel_type=channel_type,
        topic=topic,
        purpose=purpose,
        creator_id=creator_id,
        member_count=member_count,
        is_archived=is_archived,
        is_private=is_private,
        created_at=created_at,
        synced_at=now,
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": name,
            "channel_type": channel_type,
            "topic": topic,
            "purpose": purpose,
            "member_count": member_count,
            "is_archived": is_archived,
            "is_private": is_private,
            "synced_at": now,
        }
    )
    db.execute(stmt)
    db.commit()

    return get_channel(db, channel_id)


def upsert_channels_bulk(
    db: Session,
    channels: list[dict],
) -> int:
    """
    채널 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        channels: 채널 데이터 딕셔너리 리스트

    Returns:
        처리된 채널 수
    """
    if not channels:
        return 0

    now = datetime.now(timezone.utc)
    for channel in channels:
        channel["synced_at"] = now
        if "created_at" not in channel or channel["created_at"] is None:
            channel["created_at"] = now

    stmt = insert(SlackChannel).values(channels)
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


# ============================================================
# User CRUD
# ============================================================

def upsert_user(
    db: Session,
    team_id: str,
    user_id: str,
    name: str,
    real_name: str,
    display_name: str,
    deleted: bool = False,
    email: str | None = None,
    avatar_url: str | None = None,
    title: str | None = None,
    phone: str | None = None,
    tz: str | None = None,
    tz_label: str | None = None,
    is_bot: bool = False,
    is_admin: bool = False,
    is_owner: bool = False,
    is_restricted: bool = False,
    updated_at: datetime | None = None,
) -> SlackUser:
    """
    사용자 Upsert (Insert or Update)
    """
    now = datetime.now(timezone.utc)

    stmt = insert(SlackUser).values(
        team_id=team_id,
        user_id=user_id,
        name=name,
        real_name=real_name,
        display_name=display_name,
        deleted=deleted,
        email=email,
        avatar_url=avatar_url,
        title=title,
        phone=phone,
        tz=tz,
        tz_label=tz_label,
        is_bot=is_bot,
        is_admin=is_admin,
        is_owner=is_owner,
        is_restricted=is_restricted,
        updated_at=updated_at,
        synced_at=now,
    ).on_conflict_do_update(
        index_elements=["team_id", "user_id"],
        set_={
            "name": name,
            "real_name": real_name,
            "display_name": display_name,
            "deleted": deleted,
            "email": email,
            "avatar_url": avatar_url,
            "title": title,
            "phone": phone,
            "tz": tz,
            "tz_label": tz_label,
            "is_bot": is_bot,
            "is_admin": is_admin,
            "is_owner": is_owner,
            "is_restricted": is_restricted,
            "updated_at": updated_at,
            "synced_at": now,
        }
    )
    db.execute(stmt)
    db.commit()

    return get_user(db, team_id, user_id)


def upsert_users_bulk(
    db: Session,
    users: list[dict],
) -> int:
    """
    사용자 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        users: 사용자 데이터 딕셔너리 리스트

    Returns:
        처리된 사용자 수
    """
    if not users:
        return 0

    now = datetime.now(timezone.utc)
    for user in users:
        user["synced_at"] = now

    stmt = insert(SlackUser).values(users)
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
