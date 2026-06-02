from __future__ import annotations

from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
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
