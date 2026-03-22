"""
Slack Webhook 이벤트 처리 서비스

Webhook으로 수신된 채널/멤버/유저 이벤트를 파싱하고 DB에 반영.
SlackIngestionService와 달리 PGVector/Transformer 초기화 없이
메타데이터 변경만 처리하는 경량 서비스.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from catchup.connectors.slack.schemas import (
    SlackChannelEvent,
    SlackMemberEvent,
    SlackUserEvent,
    SlackUserProfile as SlackUserProfileSchema,
)
from catchup.db.slack import domain_repository

logger = logging.getLogger(__name__)


# ============================================================
# Channel Events
# ============================================================

def handle_channel_upsert(db: Session, team_id: str, event: dict) -> None:
    """
    채널 생성/이름변경 이벤트 → DB Upsert

    대상 이벤트: channel_created, channel_rename, group_created, group_rename
    Slack이 channel을 object로 전달하는 이벤트.
    """
    data = SlackChannelEvent(**event)
    channel = data.channel
    is_private = channel.is_private or channel.is_group or False

    domain_repository.upsert_channel_from_event(
        db=db,
        team_id=team_id,
        channel_id=channel.id,
        name=channel.name,
        is_private=is_private,
        creator_id=channel.creator,
    )

    logger.info(
        f"[SLACK][EVENT] Channel upserted: team={team_id}, "
        f"type={data.type}, channel={channel.id}, name={channel.name}"
    )


def handle_channel_delete(db: Session, team_id: str, event: dict) -> None:
    """
    채널 삭제 이벤트 → DB 삭제

    대상 이벤트: channel_deleted, group_deleted
    Slack이 channel을 string ID로 전달하는 이벤트.
    """
    channel_id = event.get("channel")
    if not channel_id:
        raise ValueError("Missing channel_id in channel_deleted event")

    domain_repository.delete_channel(db, channel_id)

    logger.info(
        f"[SLACK][EVENT] Channel deleted: team={team_id}, channel={channel_id}"
    )


def handle_channel_archive(db: Session, team_id: str, event: dict) -> None:
    """
    채널 아카이브/해제 이벤트 → DB 업데이트

    대상 이벤트: channel_archive, channel_unarchive, group_archive, group_unarchive
    Slack이 channel을 string ID로 전달하는 이벤트.
    """
    channel_id = event.get("channel")
    event_type = event.get("type")
    if not channel_id:
        raise ValueError("Missing channel_id in channel_archive event")

    is_archived = event_type in ("channel_archive", "group_archive")
    domain_repository.update_channel_archive(
        db,
        channel_id,
        is_archived,
    )

    logger.info(
        f"[SLACK][EVENT] Channel {'archived' if is_archived else 'unarchived'}: "
        f"team={team_id}, channel={channel_id}"
    )


# ============================================================
# Member Events
# ============================================================

def handle_member_event(db: Session, team_id: str, event: dict) -> None:
    """
    멤버십 변경 이벤트 → 채널 멤버 추가/제거

    대상 이벤트: member_joined_channel, member_left_channel
    """
    data = SlackMemberEvent(**event)

    if data.type == "member_joined_channel":
        domain_repository.add_channel_member(
            db,
            team_id,
            data.channel,
            data.user,
        )
        logger.info(
            f"[SLACK][EVENT] Member joined: team={team_id}, "
            f"channel={data.channel}, user={data.user}"
        )
    elif data.type == "member_left_channel":
        domain_repository.remove_channel_member(
            db,
            team_id,
            data.channel,
            data.user,
        )
        logger.info(
            f"[SLACK][EVENT] Member left: team={team_id}, "
            f"channel={data.channel}, user={data.user}"
        )


# ============================================================
# User Events
# ============================================================

def handle_user_event(db: Session, team_id: str, event: dict) -> None:
    """
    사용자 참여/변경 이벤트 → 유저 정보 Upsert

    대상 이벤트: team_join, user_change
    """
    data = SlackUserEvent(**event)
    user = data.user
    profile = user.profile

    user_schema = SlackUserProfileSchema(
        id=user.id,
        team_id=user.team_id,
        name=user.name,
        real_name=user.real_name or profile.get("real_name"),
        display_name=profile.get("display_name"),
        email=profile.get("email"),
        title=profile.get("title"),
        phone=profile.get("phone"),
        is_bot=user.is_bot,
        is_admin=user.is_admin or False,
        is_owner=user.is_owner or False,
        is_restricted=user.is_restricted or False,
        is_ultra_restricted=user.is_ultra_restricted or False,
        deleted=user.deleted,
        avatar_url=profile.get("image_192") or profile.get("image_72"),
        updated_at=(
            datetime.fromtimestamp(user.updated, tz=timezone.utc)
            if user.updated else None
        ),
    )

    domain_repository.upsert_users_bulk(
        db,
        team_id,
        [user_schema],
    )

    logger.info(
        f"[SLACK][EVENT] User upserted: team={team_id}, "
        f"type={data.type}, user_id={user.id}, name={user.name}"
    )
