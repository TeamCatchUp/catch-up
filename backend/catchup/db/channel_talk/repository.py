from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import cast

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import tuple_
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkChannelMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupManagerMembership,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodeMetadata,
)
from catchup.db import models as db_models


class ChannelTalkCredentialsRepository:
    """install-auth"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_connection(
        self,
        channel_id: str | None = None,
    ) -> ChannelTalkCredentialsRecord | None:
        row = _get_channel_talk_credentials(
            db=self.db,
            channel_id=channel_id,
        )
        return _to_connection_record(row)

    def list_connections(self) -> list[ChannelTalkCredentialsRecord]:
        rows = _list_channel_talk_credentials(db=self.db)
        return [
            record
            for row in rows
            if (record := _to_connection_record(row)) is not None
        ]

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

    def delete_connection(
        self,
        channel_id: str | None = None,
    ) -> bool:
        return _delete_channel_talk_credentials(
            db=self.db,
            channel_id=channel_id,
        )

    def commit(self) -> None:
        self.db.commit()


class ChannelTalkMetadataRepository:
    """metadata sync"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_connection(
        self,
        channel_id: str | None = None,
    ) -> ChannelTalkCredentialsRecord | None:
        row = _get_channel_talk_credentials(
            db=self.db,
            channel_id=channel_id,
        )
        return _to_connection_record(row)

    def get_channel_metadata(
        self,
        channel_id: str,
    ) -> ChannelTalkChannelMetadata | None:
        row = self.db.execute(
            select(db_models.ChannelTalkChannel).where(
                db_models.ChannelTalkChannel.channel_id == channel_id
            )
        ).scalar_one_or_none()
        return _to_channel_metadata(row)

    def upsert_channel_metadata(
        self,
        payload: ChannelTalkChannelMetadata,
    ) -> ChannelTalkChannelMetadata:
        row = cast(
            db_models.ChannelTalkChannel,
            _get_or_create_row(
                db=self.db,
                model=db_models.ChannelTalkChannel,
                lookup={"channel_id": payload.channel_id},
                create_values={
                    "channel_id": payload.channel_id,
                    "channel_name": payload.channel_name,
                },
            ),
        )
        _assign_channel_metadata(row, payload)
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
            select(db_models.ChannelTalkManager).where(
                db_models.ChannelTalkManager.channel_id == channel_id
            )
        ).scalars().all()
        return [_to_manager_metadata(row) for row in rows]

    def bulk_upsert_managers(
        self,
        payloads: list[ChannelTalkManagerMetadata],
    ) -> list[ChannelTalkManagerMetadata]:
        rows_by_key = _load_existing_rows(
            db=self.db,
            model=db_models.ChannelTalkManager,
            key_fields=("channel_id", "manager_id"),
            keys=[
                (_require_text(payload.channel_id, "channel_id"), payload.manager_id)
                for payload in payloads
            ],
        )
        stored_rows: list[db_models.ChannelTalkManager] = []
        for payload in payloads:
            channel_id = _require_text(payload.channel_id, "channel_id")
            key = (channel_id, payload.manager_id)
            row = cast(db_models.ChannelTalkManager | None, rows_by_key.get(key))
            if row is None:
                row = db_models.ChannelTalkManager(
                    channel_id=channel_id,
                    manager_id=payload.manager_id,
                )
                self.db.add(row)
                rows_by_key[key] = row
            _assign_manager_metadata(row, payload)
            stored_rows.append(row)
        self.db.flush()
        return [_to_manager_metadata(row) for row in stored_rows]

    def list_groups_by_channel(
        self,
        channel_id: str,
    ) -> list[ChannelTalkGroupMetadata]:
        rows = self.db.execute(
            select(db_models.ChannelTalkGroup).where(
                db_models.ChannelTalkGroup.channel_id == channel_id
            )
        ).scalars().all()
        return [_to_group_metadata(row) for row in rows]

    def bulk_upsert_groups(
        self,
        payloads: list[ChannelTalkGroupMetadata],
    ) -> list[ChannelTalkGroupMetadata]:
        rows_by_key = _load_existing_rows(
            db=self.db,
            model=db_models.ChannelTalkGroup,
            key_fields=("channel_id", "group_id"),
            keys=[
                (_require_text(payload.channel_id, "channel_id"), payload.group_id)
                for payload in payloads
            ],
        )
        stored_rows: list[db_models.ChannelTalkGroup] = []
        for payload in payloads:
            channel_id = _require_text(payload.channel_id, "channel_id")
            key = (channel_id, payload.group_id)
            row = cast(db_models.ChannelTalkGroup | None, rows_by_key.get(key))
            if row is None:
                row = db_models.ChannelTalkGroup(
                    channel_id=channel_id,
                    group_id=payload.group_id,
                    group_name=payload.group_name,
                )
                self.db.add(row)
                rows_by_key[key] = row
            _assign_group_metadata(row, payload)
            stored_rows.append(row)
        self.db.flush()
        return [_to_group_metadata(row) for row in stored_rows]

    def list_group_manager_memberships(
        self,
        *,
        channel_id: str,
        group_id: str | None = None,
    ) -> list[ChannelTalkGroupManagerMembership]:
        stmt = select(db_models.ChannelTalkGroupManager).where(
            db_models.ChannelTalkGroupManager.channel_id == channel_id
        )
        if group_id is not None:
            stmt = stmt.where(db_models.ChannelTalkGroupManager.group_id == group_id)
        rows = self.db.execute(stmt).scalars().all()
        return [_to_group_manager_membership(row) for row in rows]

    def replace_group_managers(
        self,
        *,
        channel_id: str,
        memberships: tuple[ChannelTalkGroupManagerMembership, ...],
    ) -> tuple[ChannelTalkGroupManagerMembership, ...]:
        self.db.execute(
            delete(db_models.ChannelTalkGroupManager).where(
                db_models.ChannelTalkGroupManager.channel_id == channel_id
            )
        )
        for membership in memberships:
            self.db.add(
                db_models.ChannelTalkGroupManager(
                    channel_id=membership.channel_id,
                    group_id=membership.group_id,
                    manager_id=membership.manager_id,
                )
            )
        self.db.flush()
        return memberships

    def commit(self) -> None:
        self.db.commit()


class ChannelTalkDocumentCredentialsRepository:
    """documents install-auth"""
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_base_connection(
        self,
        channel_id: str | None = None,
    ) -> ChannelTalkCredentialsRecord | None:
        row = _get_channel_talk_credentials(
            db=self.db,
            channel_id=channel_id,
        )
        return _to_connection_record(row)

    def get_document_connection(
        self,
        channel_id: str | None = None,
        space_id: str | None = None,
    ) -> ChannelTalkDocumentCredentialsRecord | None:
        row = _get_channel_talk_document_credentials(
            db=self.db,
            channel_id=channel_id,
            space_id=space_id,
        )
        return _to_document_connection_record(row)

    def list_document_connections(
        self,
        channel_id: str | None = None,
    ) -> list[ChannelTalkDocumentCredentialsRecord]:
        rows = _list_channel_talk_document_credentials(db=self.db, channel_id=channel_id)
        return [
            record
            for row in rows
            if (record := _to_document_connection_record(row)) is not None
        ]

    def upsert_document_connection(
        self,
        payload: ChannelTalkDocumentCredentialsUpsert,
    ) -> ChannelTalkDocumentCredentialsRecord:
        row = _create_or_replace_channel_talk_document_credentials(
            db=self.db,
            channel_id=payload.channel_id,
            space_id=payload.space.space_id,
            space_name=payload.space.space_name,
            access_key=payload.access_key,
            access_secret=payload.access_secret,
            credential_last_verified_at=payload.credential_last_verified_at,
            association_status=payload.association_status,
            polling_cycle_hours=payload.polling_cycle_hours,
        )
        record = _to_document_connection_record(row)
        if record is None:
            raise RuntimeError("Channel Talk Documents credentials upsert returned no record")
        return record

    def list_due_document_connections(
        self,
        *,
        now: datetime,
        stale_started_before: datetime,
    ) -> list[ChannelTalkDocumentCredentialsRecord]:
        rows = _list_due_channel_talk_document_credentials(
            db=self.db,
            now=now,
            stale_started_before=stale_started_before,
        )
        return [
            record
            for row in rows
            if (record := _to_document_connection_record(row)) is not None
        ]

    def mark_document_poll_started(
        self,
        *,
        space_id: str,
        started_at: datetime,
    ) -> bool:
        row = _get_channel_talk_document_credentials(db=self.db, space_id=space_id)
        if row is None:
            return False
        row.last_incremental_poll_started_at = started_at
        row.last_incremental_poll_error = None
        self.db.flush()
        return True

    def mark_document_poll_succeeded(
        self,
        *,
        space_id: str,
        polled_at: datetime,
    ) -> bool:
        row = _get_channel_talk_document_credentials(db=self.db, space_id=space_id)
        if row is None:
            return False
        row.last_incremental_polled_at = polled_at
        row.last_incremental_poll_started_at = None
        row.last_incremental_poll_error = None
        self.db.flush()
        return True

    def mark_document_poll_failed(
        self,
        *,
        space_id: str,
        error: str,
    ) -> bool:
        row = _get_channel_talk_document_credentials(db=self.db, space_id=space_id)
        if row is None:
            return False
        row.last_incremental_poll_started_at = None
        row.last_incremental_poll_error = str(error or "").strip()[:2000]
        self.db.flush()
        return True

    def delete_document_connection_by_space_id(self, space_id: str) -> bool:
        return _delete_rows_by_field(
            db=self.db,
            model=db_models.ChannelTalkDocumentCredentials,
            field_name="space_id",
            field_value=space_id,
        )

    def commit(self) -> None:
        self.db.commit()


class ChannelTalkDocumentMetadataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_document_connection(
        self,
        channel_id: str | None = None,
        space_id: str | None = None,
    ) -> ChannelTalkDocumentCredentialsRecord | None:
        row = _get_channel_talk_document_credentials(
            db=self.db,
            channel_id=channel_id,
            space_id=space_id,
        )
        return _to_document_connection_record(row)

    def bulk_upsert_document_authors(
        self,
        payloads: list[ChannelTalkDocumentAuthorMetadata],
    ) -> list[ChannelTalkDocumentAuthorMetadata]:
        return _bulk_upsert_document_metadata(
            db=self.db,
            model=db_models.ChannelTalkDocumentAuthor,
            key_fields=("channel_id", "space_id", "author_id"),
            payloads=payloads,
            id_field="author_id",
            assign_row=_assign_document_author_metadata,
            to_metadata=_to_document_author_metadata,
        )

    def bulk_upsert_document_nav_nodes(
        self,
        payloads: list[ChannelTalkDocumentNavNodeMetadata],
    ) -> list[ChannelTalkDocumentNavNodeMetadata]:
        return _bulk_upsert_document_metadata(
            db=self.db,
            model=db_models.ChannelTalkDocumentNavNode,
            key_fields=("channel_id", "space_id", "nav_node_id"),
            payloads=payloads,
            id_field="nav_node_id",
            assign_row=_assign_document_nav_node_metadata,
            to_metadata=_to_document_nav_node_metadata,
        )

    def commit(self) -> None:
        self.db.commit()


def _get_channel_talk_credentials(
    db: Session,
    channel_id: str | None = None,
) -> db_models.ChannelTalkCredentials | None:
    return _get_first_channel_scoped_row(
        db=db,
        model=db_models.ChannelTalkCredentials,
        channel_id=channel_id,
    )


def _list_channel_talk_credentials(
    db: Session,
) -> list[db_models.ChannelTalkCredentials]:
    stmt = select(db_models.ChannelTalkCredentials).order_by(
        db_models.ChannelTalkCredentials.id.asc()
    )
    return list(db.execute(stmt).scalars())


def _get_channel_talk_document_credentials(
    db: Session,
    channel_id: str | None = None,
    space_id: str | None = None,
) -> db_models.ChannelTalkDocumentCredentials | None:
    stmt: Any = select(db_models.ChannelTalkDocumentCredentials)
    if channel_id is not None:
        stmt = stmt.filter_by(channel_id=channel_id)
    if space_id is not None:
        stmt = stmt.filter_by(space_id=space_id)
    stmt = stmt.order_by(db_models.ChannelTalkDocumentCredentials.id.asc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _list_channel_talk_document_credentials(
    db: Session,
    channel_id: str | None = None,
) -> list[db_models.ChannelTalkDocumentCredentials]:
    stmt = select(db_models.ChannelTalkDocumentCredentials)
    if channel_id is not None:
        stmt = stmt.filter_by(channel_id=channel_id)
    stmt = stmt.order_by(db_models.ChannelTalkDocumentCredentials.id.asc())
    return list(db.execute(stmt).scalars())


def _list_due_channel_talk_document_credentials(
    db: Session,
    *,
    now: datetime,
    stale_started_before: datetime,
) -> list[db_models.ChannelTalkDocumentCredentials]:
    normalized_now = _to_utc(now)
    normalized_stale_started_before = _to_utc(stale_started_before)
    rows = _list_channel_talk_document_credentials(db=db)
    due_rows: list[db_models.ChannelTalkDocumentCredentials] = []
    for row in rows:
        try:
            association_status = ChannelTalkDocumentAssociationStatus(
                _require_text(row.association_status, "association_status")
            )
        except ValueError:
            continue
        if association_status != ChannelTalkDocumentAssociationStatus.API_VERIFIED:
            continue

        started_at = row.last_incremental_poll_started_at
        if (
            started_at is not None
            and _to_utc(started_at) > normalized_stale_started_before
        ):
            continue

        polling_cycle_hours = max(1, int(row.polling_cycle_hours or 1))
        base_at = row.last_incremental_polled_at or row.credential_last_verified_at
        if base_at is None:
            due_rows.append(row)
            continue
        if normalized_now >= _to_utc(base_at) + timedelta(hours=polling_cycle_hours):
            due_rows.append(row)
    return due_rows


def _create_or_replace_channel_talk_credentials(
    db: Session,
    channel_id: str,
    channel_name: str,
    access_key: str,
    access_secret: str,
    webhook_token: str,
    credential_last_verified_at,
) -> db_models.ChannelTalkCredentials:
    credentials = _get_channel_talk_credentials(db=db, channel_id=channel_id)

    if credentials is None:
        credentials = db_models.ChannelTalkCredentials(
            channel_id=channel_id,
            channel_name=channel_name,
            access_key=access_key,
            access_secret=access_secret,
            webhook_token=webhook_token,
            credential_last_verified_at=credential_last_verified_at,
        )
        db.add(credentials)
    else:
        _assign_credentials_values(
            credentials,
            channel_id=channel_id,
            channel_name=channel_name,
            access_key=access_key,
            access_secret=access_secret,
            webhook_token=webhook_token,
            credential_last_verified_at=credential_last_verified_at,
        )
    db.flush()
    return credentials


def _delete_channel_talk_credentials(
    db: Session,
    channel_id: str | None = None,
) -> bool:
    return _delete_channel_scoped_rows(
        db=db,
        model=db_models.ChannelTalkCredentials,
        channel_id=channel_id,
    )


def _get_first_channel_scoped_row(
    *,
    db: Session,
    model: Any,
    channel_id: str | None,
) -> Any | None:
    stmt: Any = select(model)
    if channel_id is not None:
        stmt = stmt.filter_by(channel_id=channel_id)
    stmt = stmt.order_by(model.id.asc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def _delete_channel_scoped_rows(
    *,
    db: Session,
    model: Any,
    channel_id: str | None,
) -> bool:
    stmt: Any = delete(model)
    if channel_id is not None:
        stmt = stmt.filter_by(channel_id=channel_id)

    result = cast(CursorResult, db.execute(stmt))
    db.flush()
    return (result.rowcount or 0) > 0


def _delete_rows_by_field(
    *,
    db: Session,
    model: Any,
    field_name: str,
    field_value: str,
) -> bool:
    stmt = delete(model).filter_by(**{field_name: field_value})
    result = cast(CursorResult, db.execute(stmt))
    db.flush()
    return (result.rowcount or 0) > 0


def _create_or_replace_channel_talk_document_credentials(
    db: Session,
    channel_id: str,
    space_id: str,
    space_name: str,
    access_key: str,
    access_secret: str,
    credential_last_verified_at,
    association_status: ChannelTalkDocumentAssociationStatus,
    polling_cycle_hours: int = 1,
) -> db_models.ChannelTalkDocumentCredentials:
    credentials = _get_channel_talk_document_credentials(
        db=db,
        space_id=space_id,
    )
    if credentials is None:
        credentials = db_models.ChannelTalkDocumentCredentials(
            channel_id=channel_id,
            space_id=space_id,
            space_name=space_name,
            access_key=access_key,
            access_secret=access_secret,
            credential_last_verified_at=credential_last_verified_at,
            association_status=str(association_status),
            polling_cycle_hours=max(1, int(polling_cycle_hours or 1)),
        )
        db.add(credentials)
    else:
        credentials.channel_id = channel_id
        credentials.space_id = space_id
        credentials.space_name = space_name
        credentials.access_key = access_key
        credentials.access_secret = access_secret
        credentials.credential_last_verified_at = credential_last_verified_at
        credentials.association_status = str(association_status)
        credentials.polling_cycle_hours = max(1, int(polling_cycle_hours or 1))
    db.flush()
    return credentials


def _to_connection_record(
    row: db_models.ChannelTalkCredentials | None,
) -> ChannelTalkCredentialsRecord | None:
    if row is None:
        return None

    return ChannelTalkCredentialsRecord(
        channel_id=_require_text(row.channel_id, "channel_id"),
        channel_name=_require_text(row.channel_name, "channel_name"),
        access_key=_require_text(row.access_key, "access_key"),
        access_secret=_require_text(row.access_secret, "access_secret"),
        webhook_token=_require_text(row.webhook_token, "webhook_token"),
        credential_last_verified_at=row.credential_last_verified_at,
    )


def _to_document_connection_record(
    row: db_models.ChannelTalkDocumentCredentials | None,
) -> ChannelTalkDocumentCredentialsRecord | None:
    if row is None:
        return None
    return ChannelTalkDocumentCredentialsRecord(
        channel_id=_require_text(row.channel_id, "channel_id"),
        space_id=_require_text(row.space_id, "space_id"),
        space_name=_require_text(row.space_name, "space_name"),
        access_key=_require_text(row.access_key, "access_key"),
        access_secret=_require_text(row.access_secret, "access_secret"),
        credential_last_verified_at=row.credential_last_verified_at,
        association_status=ChannelTalkDocumentAssociationStatus(
            _require_text(row.association_status, "association_status")
        ),
        polling_cycle_hours=max(1, int(row.polling_cycle_hours or 1)),
        last_incremental_polled_at=row.last_incremental_polled_at,
        last_incremental_poll_started_at=row.last_incremental_poll_started_at,
        last_incremental_poll_error=row.last_incremental_poll_error,
    )


def _to_channel_metadata(
    row: db_models.ChannelTalkChannel | None,
) -> ChannelTalkChannelMetadata | None:
    if row is None:
        return None

    return ChannelTalkChannelMetadata(
        channel_id=_require_text(row.channel_id, "channel_id"),
        channel_name=_require_text(row.channel_name, "channel_name"),
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
    row: db_models.ChannelTalkManager,
) -> ChannelTalkManagerMetadata:
    return ChannelTalkManagerMetadata(
        channel_id=_require_text(row.channel_id, "channel_id"),
        manager_id=_require_text(row.manager_id, "manager_id"),
        account_id=row.account_id,
        name=row.name,
        description=row.description,
        email=row.email,
        mobile_number=row.mobile_number,
        role_id=row.role_id,
        removed=row.removed,
        display_as_channel=row.display_as_channel,
        avatar_url=row.avatar_url,
        remote_created_at=row.remote_created_at,
    )


def _to_group_metadata(
    row: db_models.ChannelTalkGroup,
) -> ChannelTalkGroupMetadata:
    return ChannelTalkGroupMetadata(
        channel_id=_require_text(row.channel_id, "channel_id"),
        group_id=_require_text(row.group_id, "group_id"),
        group_name=_require_text(row.group_name, "group_name"),
        scope=row.scope,
        description=row.description,
        icon_url=row.icon_url,
        active=row.active,
        remote_created_at=row.remote_created_at,
        remote_updated_at=row.remote_updated_at,
        manager_ids=(),
    )


def _to_group_manager_membership(
    row: db_models.ChannelTalkGroupManager,
) -> ChannelTalkGroupManagerMembership:
    return ChannelTalkGroupManagerMembership(
        channel_id=_require_text(row.channel_id, "channel_id"),
        group_id=_require_text(row.group_id, "group_id"),
        manager_id=_require_text(row.manager_id, "manager_id"),
    )


def _to_document_author_metadata(
    row: db_models.ChannelTalkDocumentAuthor,
) -> ChannelTalkDocumentAuthorMetadata:
    return ChannelTalkDocumentAuthorMetadata(
        channel_id=_require_text(row.channel_id, "channel_id"),
        space_id=_require_text(row.space_id, "space_id"),
        author_id=_require_text(row.author_id, "author_id"),
        name=row.name,
        email=row.email,
        avatar_url=row.avatar_url,
    )


def _to_document_nav_node_metadata(
    row: db_models.ChannelTalkDocumentNavNode,
) -> ChannelTalkDocumentNavNodeMetadata:
    return ChannelTalkDocumentNavNodeMetadata(
        channel_id=_require_text(row.channel_id, "channel_id"),
        space_id=_require_text(row.space_id, "space_id"),
        nav_node_id=_require_text(row.nav_node_id, "nav_node_id"),
        parent_node_id=row.parent_node_id,
        node_type=row.node_type,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        name=row.name,
        rank=row.rank,
        language=row.language,
    )


def _get_or_create_row(
    *,
    db: Session,
    model,
    lookup: dict[str, object],
    create_values: dict[str, object],
) -> Any:
    row = db.execute(select(model).filter_by(**lookup)).scalar_one_or_none()
    if row is None:
        row = model(**create_values)
        db.add(row)
    return row


def _require_text(value: object | None, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _document_metadata_key(
    payload: ChannelTalkDocumentAuthorMetadata | ChannelTalkDocumentNavNodeMetadata,
    *,
    id_field: str,
) -> tuple[str, str, str]:
    return (
        _require_text(payload.channel_id, "channel_id"),
        _require_text(payload.space_id, "space_id"),
        _require_text(getattr(payload, id_field), id_field),
    )


def _document_metadata_keys(
    payloads: list[ChannelTalkDocumentAuthorMetadata]
    | list[ChannelTalkDocumentNavNodeMetadata],
    *,
    id_field: str,
) -> list[tuple[object, ...]]:
    return [
        _document_metadata_key(payload, id_field=id_field)
        for payload in payloads
    ]


def _bulk_upsert_document_metadata(
    *,
    db: Session,
    model,
    key_fields: tuple[str, str, str],
    payloads: list[Any],
    id_field: str,
    assign_row,
    to_metadata,
) -> list[Any]:
    rows_by_key = _load_existing_rows(
        db=db,
        model=model,
        key_fields=key_fields,
        keys=_document_metadata_keys(payloads, id_field=id_field),
    )
    stored_rows: list[Any] = []
    for payload in payloads:
        channel_id, space_id, item_id = _document_metadata_key(
            payload,
            id_field=id_field,
        )
        key = (channel_id, space_id, item_id)
        row = rows_by_key.get(key)
        if row is None:
            row = model(
                channel_id=channel_id,
                space_id=space_id,
                **{id_field: item_id},
            )
            db.add(row)
            rows_by_key[key] = row
        assign_row(row, payload)
        stored_rows.append(row)
    db.flush()
    return [to_metadata(row) for row in stored_rows]


def _load_existing_rows(
    *,
    db: Session,
    model,
    key_fields: tuple[str, ...],
    keys: list[tuple[object, ...]],
) -> dict[tuple[object, ...], object]:
    if not keys:
        return {}

    unique_keys = list(dict.fromkeys(keys))
    key_columns = tuple(getattr(model, field_name) for field_name in key_fields)
    rows = db.execute(
        select(model).where(tuple_(*key_columns).in_(unique_keys))
    ).scalars().all()
    return {
        tuple(getattr(row, field_name) for field_name in key_fields): row
        for row in rows
    }


def _assign_channel_metadata(
    row: db_models.ChannelTalkChannel,
    payload: ChannelTalkChannelMetadata,
) -> None:
    _assign_fields(
        row,
        payload,
        (
            "channel_name",
            "description",
            "bot_name",
            "homepage_url",
            "domain",
            "subdomain",
            "avatar_url",
            "country",
            "time_zone",
        ),
    )


def _assign_manager_metadata(
    row: db_models.ChannelTalkManager,
    payload: ChannelTalkManagerMetadata,
) -> None:
    _assign_fields(
        row,
        payload,
        (
            "account_id",
            "name",
            "description",
            "email",
            "mobile_number",
            "role_id",
            "removed",
            "display_as_channel",
            "avatar_url",
            "remote_created_at",
        ),
    )


def _assign_group_metadata(
    row: db_models.ChannelTalkGroup,
    payload: ChannelTalkGroupMetadata,
) -> None:
    _assign_fields(
        row,
        payload,
        (
            "group_name",
            "scope",
            "description",
            "icon_url",
            "active",
            "remote_created_at",
            "remote_updated_at",
        ),
    )


def _assign_document_author_metadata(
    row: db_models.ChannelTalkDocumentAuthor,
    payload: ChannelTalkDocumentAuthorMetadata,
) -> None:
    _assign_fields(row, payload, ("name", "email", "avatar_url"))
    row.synced_at = _utcnow()


def _assign_document_nav_node_metadata(
    row: db_models.ChannelTalkDocumentNavNode,
    payload: ChannelTalkDocumentNavNodeMetadata,
) -> None:
    _assign_fields(
        row,
        payload,
        (
            "parent_node_id",
            "node_type",
            "entity_type",
            "entity_id",
            "name",
            "rank",
            "language",
        ),
    )
    row.synced_at = _utcnow()


def _assign_fields(row: object, payload: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        setattr(row, field_name, getattr(payload, field_name))


def _assign_credentials_values(
    row: db_models.ChannelTalkCredentials,
    *,
    channel_id: str,
    channel_name: str,
    access_key: str,
    access_secret: str,
    webhook_token: str,
    credential_last_verified_at,
) -> None:
    row.channel_id = channel_id
    row.channel_name = channel_name
    row.access_key = access_key
    row.access_secret = access_secret
    row.webhook_token = webhook_token
    row.credential_last_verified_at = credential_last_verified_at
