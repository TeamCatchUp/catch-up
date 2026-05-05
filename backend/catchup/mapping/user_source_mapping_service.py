from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import and_
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
from catchup.mapping.user_source_mapping_models import MappedSourceInfo
from catchup.mapping.user_source_mapping_models import MappingStatusCount
from catchup.mapping.user_source_mapping_models import MappingStatusResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingItem
from catchup.mapping.user_source_mapping_models import UserSourceMappingRefreshResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingResponse
from catchup.mapping.user_source_mapping_models import UserSourceMappingStatus

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
    SourceType.CONFLUENCE: "atlassian",
    SourceType.CHANNEL_TALK: "channel_talk",
}

FULL_MAPPING_SOURCE_GROUPS: tuple[tuple[SourceType, ...], ...] = (
    (SourceType.JIRA, SourceType.CONFLUENCE),
    (SourceType.SLACK,),
    (SourceType.GITHUB,),
    (SourceType.CHANNEL_TALK,),
)


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
        mapping_status: UserSourceMappingStatus = UserSourceMappingStatus.ALL,
        page: int = 1,
        size: int = 50,
    ) -> UserSourceMappingResponse:
        with self._session() as db:
            mapped_users_stmt = select(
                distinct(UserSourceMapping.user_id).label("user_id")
            ).where(UserSourceMapping.source_type.in_(TRACKED_USER_MAPPING_SOURCES))
            mapped_users = mapped_users_stmt.subquery()
            base_stmt = (
                select(User, OAuthUser.sub.label("sub"))
                .join(mapped_users, mapped_users.c.user_id == User.id)
                .outerjoin(OAuthUser, OAuthUser.user_id == User.id)
            )
            full_mapping_condition = self._full_mapping_condition()
            if mapping_status == UserSourceMappingStatus.FULL:
                base_stmt = base_stmt.where(full_mapping_condition)
            elif mapping_status == UserSourceMappingStatus.PARTIAL:
                base_stmt = base_stmt.where(~full_mapping_condition)

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
            external_ids_by_source: dict[SourceType, set[str]] = {
                source_type: set() for source_type in TRACKED_USER_MAPPING_SOURCES
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
                    normalized_source_type = SourceType(source_type)
                    mappings_by_user[user_id][
                        normalized_source_type
                    ] = external_user_identifier
                    external_ids_by_source[normalized_source_type].add(
                        external_user_identifier
                    )

            source_info_by_source = self._build_source_info_by_source(
                db=db,
                external_ids_by_source=external_ids_by_source,
            )

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
                    source_info = source_info_by_source[source_type].get(
                        external_user_identifier
                    )
                    if (
                        field_name == "atlassian"
                        and item_payload.get("atlassian") is not None
                        and source_type != SourceType.JIRA
                    ):
                        continue
                    item_payload[field_name] = source_info
                items.append(UserSourceMappingItem(**item_payload))

            return UserSourceMappingResponse(
                total=total,
                page=page,
                size=size,
                items=items,
            )

    def _full_mapping_condition(self):
        return and_(
            *(
                self._has_mapping_for_sources(source_group)
                for source_group in FULL_MAPPING_SOURCE_GROUPS
            )
        )

    def _has_mapping_for_sources(self, source_types: tuple[SourceType, ...]):
        return (
            select(UserSourceMapping.user_id)
            .where(
                UserSourceMapping.user_id == User.id,
                UserSourceMapping.source_type.in_(source_types),
            )
            .exists()
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
            new_mappings: list[UserSourceMapping] = []

            for source_type in TRACKED_USER_MAPPING_SOURCES:
                source_key = _source_key(source_type)
                unmapped_users = [
                    user for user in users if (user.id, source_type) not in existing
                ]
                skipped_existing[source_key] = len(users) - len(unmapped_users)

                external_ids_by_email = self._find_external_ids_by_email(
                    db=db,
                    source_type=source_type,
                    emails=[user.email for user in unmapped_users],
                )
                for user in unmapped_users:
                    external_user_identifier = external_ids_by_email.get(
                        user.email.lower()
                    )
                    if not external_user_identifier:
                        not_found[source_key] += 1
                        continue

                    new_mappings.append(
                        UserSourceMapping(
                            user_id=user.id,
                            source_type=source_type,
                            external_user_identifier=external_user_identifier,
                        )
                    )
                    inserted[source_key] += 1
                    existing.add((user.id, source_type))

            db.add_all(new_mappings)

            db.commit()
            return UserSourceMappingRefreshResponse(
                scanned_users=len(users),
                inserted=inserted,
                skipped_existing=skipped_existing,
                not_found=not_found,
            )

    def _find_external_ids_by_email(
        self,
        *,
        db: Session,
        source_type: SourceType,
        emails: list[str],
    ) -> dict[str, str]:
        normalized_emails = {
            email.lower() for email in emails if email and email.strip()
        }
        if not normalized_emails:
            return {}

        if source_type == SourceType.JIRA:
            rows = db.execute(
                select(JiraUser.email_address, JiraUser.account_id)
                .where(
                    JiraUser.email_address.is_not(None),
                    JiraUser.account_id.is_not(None),
                    func.lower(JiraUser.email_address).in_(normalized_emails),
                    JiraUser.account_type == JiraAccountType.ATLASSIAN,
                )
                .order_by(JiraUser.synced_at.desc())
            ).all()
        elif source_type == SourceType.SLACK:
            rows = db.execute(
                select(SlackUser.email, SlackUser.user_id)
                .where(
                    SlackUser.email.is_not(None),
                    SlackUser.user_id.is_not(None),
                    func.lower(SlackUser.email).in_(normalized_emails),
                    SlackUser.is_bot.is_(False),
                )
                .order_by(SlackUser.synced_at.desc())
            ).all()
        elif source_type == SourceType.GITHUB:
            rows = db.execute(
                select(GitHubUser.email, GitHubUser.login).where(
                    GitHubUser.email.is_not(None),
                    GitHubUser.login.is_not(None),
                    func.lower(GitHubUser.email).in_(normalized_emails),
                )
            ).all()
        elif source_type == SourceType.CONFLUENCE:
            rows = db.execute(
                select(ConfluenceUser.email, ConfluenceUser.account_id)
                .where(
                    ConfluenceUser.email.is_not(None),
                    ConfluenceUser.account_id.is_not(None),
                    func.lower(ConfluenceUser.email).in_(normalized_emails),
                    ConfluenceUser.account_type == "atlassian",
                )
                .order_by(ConfluenceUser.synced_at.desc())
            ).all()
        elif source_type == SourceType.CHANNEL_TALK:
            rows = db.execute(
                select(ChannelTalkManager.email, ChannelTalkManager.manager_id).where(
                    ChannelTalkManager.email.is_not(None),
                    ChannelTalkManager.manager_id.is_not(None),
                    func.lower(ChannelTalkManager.email).in_(normalized_emails),
                    ChannelTalkManager.removed.is_not(True),
                )
            ).all()
        else:
            return {}

        external_ids_by_email: dict[str, str] = {}
        for email, external_user_identifier in rows:
            if email and external_user_identifier:
                external_ids_by_email.setdefault(
                    email.lower(), external_user_identifier
                )
        return external_ids_by_email

    def _build_source_info_by_source(
        self,
        *,
        db: Session,
        external_ids_by_source: dict[SourceType, set[str]],
    ) -> dict[SourceType, dict[str, MappedSourceInfo]]:
        source_info_by_source: dict[SourceType, dict[str, MappedSourceInfo]] = {
            source_type: {} for source_type in TRACKED_USER_MAPPING_SOURCES
        }

        jira_ids = external_ids_by_source[SourceType.JIRA]
        if jira_ids:
            rows = db.scalars(
                select(JiraUser)
                .where(
                    JiraUser.account_id.in_(jira_ids),
                    JiraUser.account_type == JiraAccountType.ATLASSIAN,
                )
                .order_by(JiraUser.synced_at.desc())
            ).all()
            for row in rows:
                source_info_by_source[SourceType.JIRA].setdefault(
                    row.account_id,
                    MappedSourceInfo(
                        name=row.display_name,
                        identifier=row.email_address,
                        picture=row.avatar_url,
                    ),
                )

        slack_ids = external_ids_by_source[SourceType.SLACK]
        if slack_ids:
            rows = db.scalars(
                select(SlackUser)
                .where(
                    SlackUser.user_id.in_(slack_ids),
                    SlackUser.is_bot.is_(False),
                )
                .order_by(SlackUser.synced_at.desc())
            ).all()
            for row in rows:
                source_info_by_source[SourceType.SLACK].setdefault(
                    row.user_id,
                    MappedSourceInfo(
                        name=row.real_name or row.display_name,
                        identifier=row.email,
                        picture=row.avatar_url,
                    ),
                )

        github_ids = external_ids_by_source[SourceType.GITHUB]
        if github_ids:
            rows = db.scalars(
                select(GitHubUser).where(GitHubUser.login.in_(github_ids))
            ).all()
            for row in rows:
                source_info_by_source[SourceType.GITHUB][row.login] = MappedSourceInfo(
                    name=row.name or row.login,
                    identifier=row.email,
                    picture=row.avatar_url,
                )

        confluence_ids = external_ids_by_source[SourceType.CONFLUENCE]
        if confluence_ids:
            rows = db.scalars(
                select(ConfluenceUser)
                .where(
                    ConfluenceUser.account_id.in_(confluence_ids),
                    ConfluenceUser.account_type == "atlassian",
                )
                .order_by(ConfluenceUser.synced_at.desc())
            ).all()
            for row in rows:
                source_info_by_source[SourceType.CONFLUENCE].setdefault(
                    row.account_id,
                    MappedSourceInfo(
                        name=row.display_name or row.public_name,
                        identifier=row.email,
                        picture=row.avatar_url,
                    ),
                )

        channel_talk_ids = external_ids_by_source[SourceType.CHANNEL_TALK]
        if channel_talk_ids:
            rows = db.scalars(
                select(ChannelTalkManager).where(
                    ChannelTalkManager.manager_id.in_(channel_talk_ids),
                    ChannelTalkManager.removed.is_not(True),
                )
            )
            for row in rows:
                source_info_by_source[SourceType.CHANNEL_TALK].setdefault(
                    row.manager_id,
                    MappedSourceInfo(
                        name=row.name,
                        identifier=row.email,
                        picture=row.avatar_url,
                    ),
                )

        return source_info_by_source
