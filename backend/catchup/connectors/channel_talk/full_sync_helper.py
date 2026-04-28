from __future__ import annotations

from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_BOOTSTRAP_TARGET_ID,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.engine import SessionLocal

CHANNEL_TALK_FULL_SYNC_TARGET_ID = CHANNEL_TALK_BOOTSTRAP_TARGET_ID


def load_channel_talk_connection() -> ChannelTalkCredentialsRecord | None:
    with SessionLocal() as db:
        return ChannelTalkCredentialsRepository(db).get_connection()


def require_channel_talk_channel_id(
    scope_id: str,
    *,
    empty_message: str = "channel_talk channel_id(scope_id) is empty",
) -> str:
    channel_id = scope_id.strip()
    if not channel_id:
        raise ValueError(empty_message)
    return channel_id
