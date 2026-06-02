from __future__ import annotations

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.engine import SessionLocal


def load_channel_talk_connection_by_id(
    credential_id: int,
) -> ChannelTalkCredentialsRecord | None:
    with SessionLocal() as db:
        return ChannelTalkCredentialsRepository(db).get_connection_by_id(
            credential_id=credential_id,
        )
