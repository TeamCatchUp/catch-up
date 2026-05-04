from __future__ import annotations

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
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


def is_verified_channel_talk_document_connection(
    connection: ChannelTalkDocumentCredentialsRecord | None,
    *,
    channel_id: str,
) -> bool:
    return (
        connection is not None
        and connection.channel_id == channel_id
        and connection.association_status
        == ChannelTalkDocumentAssociationStatus.API_VERIFIED
    )


def require_channel_talk_channel_id(
    scope_id: str,
    *,
    empty_message: str = "channel_talk channel_id(scope_id) is empty",
) -> str:
    channel_id = scope_id.strip()
    if not channel_id:
        raise ValueError(empty_message)
    return channel_id
