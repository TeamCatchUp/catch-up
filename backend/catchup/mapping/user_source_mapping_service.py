from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.models import ChannelTalkManager
from catchup.db.models import ConfluenceUser
from catchup.db.models import GitHubUser
from catchup.db.models import JiraAccountType
from catchup.db.models import JiraUser
from catchup.db.models import OAuthUser
from catchup.db.models import SlackUser
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.db.models import UserSourceMapping
from catchup.db.user_source_mapping import (
    find_external_user_id_by_email_case_insensitive,
)
from catchup.db.user_source_mapping import insert_user_source_mapping_if_absent
from catchup.mapping.user_source_mapping_models import MappedSourceInfo
from catchup.mapping.user_source_mapping_models import MappingStatusCount
from catchup.mapping.user_source_mapping_models import MappingStatusResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingItem
from catchup.mapping.user_source_mapping_models import UserSourceMappingRefreshResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingResponse

SessionFactory = Callable[[], Session]

TRACKED_USER_MAPPING_SOURCES: tuple[SourceType, ...] = (
    SourceType.JIRA,
    SourceType.SLACK,
    SourceType.GITHUB,
    SourceType.CONFLUENCE,
    SourceType.CHANNEL_TALK,
)

ITEM_FIELD_BY_SOURCE = {
    SourceType.JIRA: "atlassian",
    SourceType.SLACK: "slack",
    SourceType.GITHUB: "github",
    SourceType.CONFLUENCE: "confluence",
    SourceType.CHANNEL_TALK: "channel_talk",
}


def _source_key(source_type: SourceType) -> str:
    return source_type.value


def _empty_source_counts() -> dict[str, int]:
    return {_source_key(source_type): 0 for source_type in TRACKED_USER_MAPPING_SOURCES}


def _mapping_status_count(total_users: int, mapped: int) -> MappingStatusCount:
    return MappingStatusCount(users=total_users, mapped=mapped)


class UserSourceMappingApplication:
    def __init__(
        self,
        *,
        db: Session | None = None,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        self.db = db
        self.session_factory = session_factory

    @contextmanager
    def _session(self) -> Iterator[Session]:
        if self.db is not None:
            yield self.db
            return

        with self.session_factory() as db:
            yield db

    def get_mapping_status(self) -> MappingStatusResponse:
        with self._session() as db:
            total_users = db.scalar(select(func.count()).select_from(User)) or 0
            rows = db.execute(
                select(
                    UserSourceMapping.source_type,
                    func.count(distinct(UserSourceMapping.user_id)),
                )
                .where(UserSourceMapping.source_type.in_(TRACKED_USER_MAPPING_SOURCES))
                .group_by(UserSourceMapping.source_type)
            ).all()
            mapped_by_source = {
                SourceType(source_type): count for source_type, count in rows
            }
            payload = {
                _source_key(source_type): _mapping_status_count(
                    total_users,
                    mapped_by_source.get(source_type, 0),
                )
                for source_type in TRACKED_USER_MAPPING_SOURCES
            }
            return MappingStatusResponse(**payload)

    def list_user_source_mappings(
        self,
        *,
        source_type_filter: SourceType | None = None,
        page: int = 1,
        size: int = 50,
    ) -> UserSourceMappingResponse:
        with self._session() as db:
            mapped_users_stmt = select(
                distinct(UserSourceMapping.user_id).label("user_id")
            ).where(UserSourceMapping.source_type.in_(TRACKED_USER_MAPPING_SOURCES))
            if source_type_filter is not None:
                mapped_users_stmt = mapped_users_stmt.where(
                    UserSourceMapping.source_type == source_type_filter
                )
            mapped_users = mapped_users_stmt.subquery()

            base_stmt = (
                select(User, OAuthUser.sub.label("sub"))
                .join(mapped_users, mapped_users.c.user_id == User.id)
                .outerjoin(OAuthUser, OAuthUser.user_id == User.id)
            )

            total = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
            offset = (page - 1) * size
            rows = db.execute(
                base_stmt.order_by(User.email).offset(offset).limit(size)
            ).all()

            users = [row.User for row in rows]
            user_ids = [user.id for user in users]
            mappings_by_user: dict[int, dict[SourceType, str]] = {
                user_id: {} for user_id in user_ids
            }

            if user_ids:
                mapping_rows = db.execute(
                    select(
                        UserSourceMapping.user_id,
                        UserSourceMapping.source_type,
                        UserSourceMapping.external_user_identifier,
                    ).where(
                        UserSourceMapping.user_id.in_(user_ids),
                        UserSourceMapping.source_type.in_(TRACKED_USER_MAPPING_SOURCES),
                    )
                ).all()
                for user_id, source_type, external_user_identifier in mapping_rows:
                    mappings_by_user[user_id][
                        SourceType(source_type)
                    ] = external_user_identifier

            items: list[UserSourceMappingItem] = []
            for row in rows:
                user = row.User
                item_payload = {
                    "user_id": user.id,
                    "sub": row.sub,
                    "name": user.name,
                    "email": user.email,
                }
                for source_type, external_user_identifier in mappings_by_user[
                    user.id
                ].items():
                    field_name = ITEM_FIELD_BY_SOURCE[source_type]
                    item_payload[field_name] = self._build_source_info(
                        db=db,
                        source_type=source_type,
                        external_user_identifier=external_user_identifier,
                    )
                items.append(UserSourceMappingItem(**item_payload))

            return UserSourceMappingResponse(
                total=total,
                page=page,
                size=size,
                items=items,
            )

    def refresh_user_source_mappings(self) -> UserSourceMappingRefreshResponse:
        with self._session() as db:
            users = db.scalars(select(User).order_by(User.email)).all()
            existing_rows = db.execute(
                select(UserSourceMapping.user_id, UserSourceMapping.source_type).where(
                    UserSourceMapping.source_type.in_(TRACKED_USER_MAPPING_SOURCES)
                )
            ).all()
            existing = {
                (user_id, SourceType(source_type))
                for user_id, source_type in existing_rows
            }

            inserted = _empty_source_counts()
            skipped_existing = _empty_source_counts()
            not_found = _empty_source_counts()

            for user in users:
                for source_type in TRACKED_USER_MAPPING_SOURCES:
                    source_key = _source_key(source_type)
                    mapping_key = (user.id, source_type)
                    if mapping_key in existing:
                        skipped_existing[source_key] += 1
                        continue

                    external_user_identifier = find_external_user_id_by_email_case_insensitive(
                        db,
                        source_type,
                        user.email,
                    )
                    if not external_user_identifier:
                        not_found[source_key] += 1
                        continue

                    was_inserted = insert_user_source_mapping_if_absent(
                        db,
                        user_id=user.id,
                        source_type=source_type,
                        external_user_identifier=external_user_identifier,
                    )
                    if was_inserted:
                        inserted[source_key] += 1
                        existing.add(mapping_key)
                    else:
                        skipped_existing[source_key] += 1

            db.commit()
            return UserSourceMappingRefreshResponse(
                scanned_users=len(users),
                inserted=inserted,
                skipped_existing=skipped_existing,
                not_found=not_found,
            )

    def _build_source_info(
        self,
        *,
        db: Session,
        source_type: SourceType,
        external_user_identifier: str,
    ) -> MappedSourceInfo | None:
        if source_type == SourceType.JIRA:
            row = (
                db.query(JiraUser)
                .filter(
                    JiraUser.account_id == external_user_identifier,
                    JiraUser.account_type == JiraAccountType.ATLASSIAN,
                )
                .order_by(JiraUser.synced_at.desc())
                .first()
            )
            if not row:
                return None
            return MappedSourceInfo(
                name=row.display_name,
                identifier=row.email_address,
                picture=row.avatar_url,
            )

        if source_type == SourceType.SLACK:
            row = (
                db.query(SlackUser)
                .filter(
                    SlackUser.user_id == external_user_identifier,
                    SlackUser.is_bot == False,  # noqa: E712
                )
                .order_by(SlackUser.synced_at.desc())
                .first()
            )
            if not row:
                return None
            return MappedSourceInfo(
                name=row.real_name or row.display_name,
                identifier=row.email,
                picture=row.avatar_url,
            )

        if source_type == SourceType.GITHUB:
            row = (
                db.query(GitHubUser)
                .filter(GitHubUser.login == external_user_identifier)
                .first()
            )
            if not row:
                return None
            return MappedSourceInfo(
                name=row.name or row.login,
                identifier=row.email,
                picture=row.avatar_url,
            )

        if source_type == SourceType.CONFLUENCE:
            row = (
                db.query(ConfluenceUser)
                .filter(
                    ConfluenceUser.account_id == external_user_identifier,
                    ConfluenceUser.account_type == "atlassian",
                )
                .order_by(ConfluenceUser.synced_at.desc())
                .first()
            )
            if not row:
                return None
            return MappedSourceInfo(
                name=row.display_name or row.public_name,
                identifier=row.email,
                picture=row.avatar_url,
            )

        if source_type == SourceType.CHANNEL_TALK:
            row = (
                db.query(ChannelTalkManager)
                .filter(
                    ChannelTalkManager.manager_id == external_user_identifier,
                    ChannelTalkManager.removed.is_not(True),
                )
                .first()
            )
            if not row:
                return None
            return MappedSourceInfo(
                name=row.name,
                identifier=row.email,
                picture=row.avatar_url,
            )

        return None
