from __future__ import annotations

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.channel_talk.repository import ChannelTalkDocumentCredentialsRepository
from catchup.db.engine import SessionLocal


def load_channel_talk_connection(
    channel_id: str | None = None,
) -> ChannelTalkCredentialsRecord | None:
    with SessionLocal() as db:
        return ChannelTalkCredentialsRepository(db).get_connection(
            channel_id=channel_id,
        )


def load_channel_talk_connection_by_id(
    credential_id: int,
) -> ChannelTalkCredentialsRecord | None:
    with SessionLocal() as db:
        return ChannelTalkCredentialsRepository(db).get_connection_by_id(
            credential_id=credential_id,
        )


def list_channel_talk_connections() -> list[ChannelTalkCredentialsRecord]:
    with SessionLocal() as db:
        return ChannelTalkCredentialsRepository(db).list_connections()


def load_channel_talk_document_connection(
    channel_id: str | None = None,
    space_id: str | None = None,
) -> ChannelTalkDocumentCredentialsRecord | None:
    with SessionLocal() as db:
        return ChannelTalkDocumentCredentialsRepository(db).get_document_connection(
            channel_id=channel_id,
            space_id=space_id,
        )


def list_channel_talk_document_connections(
    channel_id: str | None = None,
) -> list[ChannelTalkDocumentCredentialsRecord]:
    with SessionLocal() as db:
        return ChannelTalkDocumentCredentialsRepository(db).list_document_connections(
            channel_id=channel_id,
        )
