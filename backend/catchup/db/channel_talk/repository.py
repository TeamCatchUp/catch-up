from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsUpsert
from catchup.db.models import ChannelTalkCredentials


def get_channel_talk_credentials(
    db: Session,
) -> ChannelTalkCredentials | None:
    stmt = select(ChannelTalkCredentials).order_by(ChannelTalkCredentials.id.asc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def create_or_replace_channel_talk_credentials(
    db: Session,
    channel_id: str,
    channel_name: str,
    access_key: str,
    access_secret: str,
    webhook_token: str,
    credential_last_verified_at: datetime,
) -> ChannelTalkCredentials:
    existing = get_channel_talk_credentials(db=db)

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


def delete_channel_talk_credentials(db: Session) -> bool:
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


class ChannelTalkCredentialsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_connection(self) -> ChannelTalkCredentialsRecord | None:
        row = get_channel_talk_credentials(db=self.db)
        return _to_connection_record(row)

    def upsert_connection(
        self,
        payload: ChannelTalkCredentialsUpsert,
    ) -> ChannelTalkCredentialsRecord:
        row = create_or_replace_channel_talk_credentials(
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
        return delete_channel_talk_credentials(db=self.db)

    def commit(self) -> None:
        self.db.commit()
