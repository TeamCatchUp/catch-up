from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.schemas import ChannelTalkChannelMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsUpsert
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupManagerMembership
from catchup.connectors.channel_talk.schemas import ChannelTalkGroupMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadata
from catchup.db.models import ChannelTalkChannel as ChannelTalkChannelRow
from catchup.db.models import ChannelTalkCredentials
from catchup.db.models import ChannelTalkGroup as ChannelTalkGroupRow
from catchup.db.models import ChannelTalkGroupManager as ChannelTalkGroupManagerRow
from catchup.db.models import ChannelTalkManager as ChannelTalkManagerRow


class ChannelTalkCredentialsRepository:
    """install-auth"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_connection(self) -> ChannelTalkCredentialsRecord | None:
        row = _get_channel_talk_credentials(db=self.db)
        return _to_connection_record(row)

    def upsert_connection(
        self,
        payload: ChannelTalkCredentialsUpsert,
    ) -> ChannelTalkCredentialsRecord:
        row = _create_or_replace_channel_talk_credentials(
            db=self.db,
            channel_id=payload.current_channel.channel_id,
            channel_name=payload.current_channel.channel_name,
            access_key=payload.access_key,
            access_secret=payload.access_secret,
            webhook_token=payload.webhook_token,
            credential_last_verified_at=payload.credential_last_verified_at,
        )
        record = _to_connection_record(row)
        if record is None:
            raise RuntimeError("Channel Talk credentials upsert returned no record")
        return record

    def delete_connection(self) -> bool:
        return _delete_channel_talk_credentials(db=self.db)

    def commit(self) -> None:
        self.db.commit()


class ChannelTalkMetadataRepository:
    """metadata sync"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_connection(self) -> ChannelTalkCredentialsRecord | None:
        row = _get_channel_talk_credentials(db=self.db)
        return _to_connection_record(row)

    def get_channel_metadata(
        self,
        channel_id: str,
    ) -> ChannelTalkChannelMetadata | None:
        row = self.db.execute(
            select(ChannelTalkChannelRow).where(ChannelTalkChannelRow.channel_id == channel_id)
        ).scalar_one_or_none()
        return _to_channel_metadata(row)

    def upsert_channel_metadata(
        self,
        payload: ChannelTalkChannelMetadata,
    ) -> ChannelTalkChannelMetadata:
        row = self.db.execute(
            select(ChannelTalkChannelRow).where(
                ChannelTalkChannelRow.channel_id == payload.channel_id
            )
        ).scalar_one_or_none()
        if row is None:
            row = ChannelTalkChannelRow(
                channel_id=payload.channel_id,
                channel_name=payload.channel_name,
            )
            self.db.add(row)

        row.channel_name = payload.channel_name
        row.description = payload.description
        row.bot_name = payload.bot_name
        row.homepage_url = payload.homepage_url
        row.domain = payload.domain
        row.subdomain = payload.subdomain
        row.avatar_url = payload.avatar_url
        row.country = payload.country
        row.time_zone = payload.time_zone
        self.db.flush()

        record = _to_channel_metadata(row)
        if record is None:
            raise RuntimeError("Channel Talk channel metadata upsert returned no record")
        return record

    def list_managers_by_channel(
        self,
        channel_id: str,
    ) -> list[ChannelTalkManagerMetadata]:
        rows = self.db.execute(
            select(ChannelTalkManagerRow).where(ChannelTalkManagerRow.channel_id == channel_id)
        ).scalars().all()
        return [_to_manager_metadata(row) for row in rows]

    def bulk_upsert_managers(
        self,
        payloads: list[ChannelTalkManagerMetadata],
    ) -> list[ChannelTalkManagerMetadata]:
        stored: list[ChannelTalkManagerMetadata] = []
        for payload in payloads:
            row = self.db.execute(
                select(ChannelTalkManagerRow).where(
                    ChannelTalkManagerRow.channel_id == payload.channel_id,
                    ChannelTalkManagerRow.manager_id == payload.manager_id,
                )
            ).scalar_one_or_none()
            if row is None:
                row = ChannelTalkManagerRow(
                    channel_id=payload.channel_id,
                    manager_id=payload.manager_id,
                )
                self.db.add(row)

            row.account_id = payload.account_id
            row.name = payload.name
            row.description = payload.description
            row.email = payload.email
            row.mobile_number = payload.mobile_number
            row.role = payload.role
            row.removed = payload.removed
            row.display_as_channel = payload.display_as_channel
            row.avatar_url = payload.avatar_url
            row.remote_created_at = payload.remote_created_at
            self.db.flush()
            stored.append(_to_manager_metadata(row))
        return stored

    def list_groups_by_channel(
        self,
        channel_id: str,
    ) -> list[ChannelTalkGroupMetadata]:
        rows = self.db.execute(
            select(ChannelTalkGroupRow).where(ChannelTalkGroupRow.channel_id == channel_id)
        ).scalars().all()
        return [_to_group_metadata(row) for row in rows]

    def bulk_upsert_groups(
        self,
        payloads: list[ChannelTalkGroupMetadata],
    ) -> list[ChannelTalkGroupMetadata]:
        stored: list[ChannelTalkGroupMetadata] = []
        for payload in payloads:
            row = self.db.execute(
                select(ChannelTalkGroupRow).where(
                    ChannelTalkGroupRow.channel_id == payload.channel_id,
                    ChannelTalkGroupRow.group_id == payload.group_id,
                )
            ).scalar_one_or_none()
            if row is None:
                row = ChannelTalkGroupRow(
                    channel_id=payload.channel_id,
                    group_id=payload.group_id,
                    group_name=payload.group_name,
                )
                self.db.add(row)

            row.group_name = payload.group_name
            row.scope = payload.scope
            row.description = payload.description
            row.icon_url = payload.icon_url
            row.active = payload.active
            row.remote_created_at = payload.remote_created_at
            row.remote_updated_at = payload.remote_updated_at
            self.db.flush()
            stored.append(_to_group_metadata(row))
        return stored

    def list_group_manager_memberships(
        self,
        *,
        channel_id: str,
        group_id: str | None = None,
    ) -> list[ChannelTalkGroupManagerMembership]:
        stmt = select(ChannelTalkGroupManagerRow).where(
            ChannelTalkGroupManagerRow.channel_id == channel_id
        )
        if group_id is not None:
            stmt = stmt.where(ChannelTalkGroupManagerRow.group_id == group_id)
        rows = self.db.execute(stmt).scalars().all()
        return [_to_group_manager_membership(row) for row in rows]

    def replace_group_managers(
        self,
        *,
        channel_id: str,
        memberships: tuple[ChannelTalkGroupManagerMembership, ...],
    ) -> tuple[ChannelTalkGroupManagerMembership, ...]:
        self.db.execute(
            delete(ChannelTalkGroupManagerRow).where(
                ChannelTalkGroupManagerRow.channel_id == channel_id
            )
        )
        for membership in memberships:
            self.db.add(
                ChannelTalkGroupManagerRow(
                    channel_id=membership.channel_id,
                    group_id=membership.group_id,
                    manager_id=membership.manager_id,
                )
            )
        self.db.flush()
        return memberships

    def commit(self) -> None:
        self.db.commit()


def _get_channel_talk_credentials(
    db: Session,
) -> ChannelTalkCredentials | None:
    stmt = select(ChannelTalkCredentials).order_by(ChannelTalkCredentials.id.asc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _create_or_replace_channel_talk_credentials(
    db: Session,
    channel_id: str,
    channel_name: str,
    access_key: str,
    access_secret: str,
    webhook_token: str,
    credential_last_verified_at: datetime,
) -> ChannelTalkCredentials:
    existing = _get_channel_talk_credentials(db=db)

    if existing is not None:
        existing.channel_id = channel_id
        existing.channel_name = channel_name
        existing.access_key = access_key
        existing.access_secret = access_secret
        existing.webhook_token = webhook_token
        existing.credential_last_verified_at = credential_last_verified_at
        db.flush()
        return existing

    credentials = ChannelTalkCredentials(
        channel_id=channel_id,
        channel_name=channel_name,
        access_key=access_key,
        access_secret=access_secret,
        webhook_token=webhook_token,
        credential_last_verified_at=credential_last_verified_at,
    )
    db.add(credentials)
    db.flush()
    return credentials


def _delete_channel_talk_credentials(db: Session) -> bool:
    stmt = delete(ChannelTalkCredentials)
    result = db.execute(stmt)
    db.flush()
    return (result.rowcount or 0) > 0


def _to_connection_record(
    row: ChannelTalkCredentials | None,
) -> ChannelTalkCredentialsRecord | None:
    if row is None:
        return None

    return ChannelTalkCredentialsRecord(
        channel_id=row.channel_id,
        channel_name=row.channel_name,
        access_key=row.access_key,
        access_secret=row.access_secret,
        webhook_token=row.webhook_token,
        credential_last_verified_at=row.credential_last_verified_at,
    )


def _to_channel_metadata(
    row: ChannelTalkChannelRow | None,
) -> ChannelTalkChannelMetadata | None:
    if row is None:
        return None

    return ChannelTalkChannelMetadata(
        channel_id=row.channel_id,
        channel_name=row.channel_name,
        description=row.description,
        bot_name=row.bot_name,
        homepage_url=row.homepage_url,
        domain=row.domain,
        subdomain=row.subdomain,
        avatar_url=row.avatar_url,
        country=row.country,
        time_zone=row.time_zone,
    )


def _to_manager_metadata(
    row: ChannelTalkManagerRow,
) -> ChannelTalkManagerMetadata:
    return ChannelTalkManagerMetadata(
        channel_id=row.channel_id,
        manager_id=row.manager_id,
        account_id=row.account_id,
        name=row.name,
        description=row.description,
        email=row.email,
        mobile_number=row.mobile_number,
        role=row.role,
        removed=row.removed,
        display_as_channel=row.display_as_channel,
        avatar_url=row.avatar_url,
        remote_created_at=row.remote_created_at,
    )


def _to_group_metadata(
    row: ChannelTalkGroupRow,
) -> ChannelTalkGroupMetadata:
    return ChannelTalkGroupMetadata(
        channel_id=row.channel_id,
        group_id=row.group_id,
        group_name=row.group_name,
        scope=row.scope,
        description=row.description,
        icon_url=row.icon_url,
        active=row.active,
        remote_created_at=row.remote_created_at,
        remote_updated_at=row.remote_updated_at,
        manager_ids=(),
    )


def _to_group_manager_membership(
    row: ChannelTalkGroupManagerRow,
) -> ChannelTalkGroupManagerMembership:
    return ChannelTalkGroupManagerMembership(
        channel_id=row.channel_id,
        group_id=row.group_id,
        manager_id=row.manager_id,
    )

