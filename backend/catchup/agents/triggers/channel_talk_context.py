from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_transformer import (
    UserChatTransformer,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.sync.ingestion.schemas import SyncWindow

CHANNEL_TALK_USER_CHAT_CONTEXT_KEY = "channel_talk_user_chat_context"
CHANNEL_TALK_USER_CHAT_ID_KEY = "channel_talk_user_chat_id"
CHANNEL_TALK_CHANNEL_ID_KEY = "channel_talk_channel_id"


async def build_channel_talk_user_chat_inputs(
    payload: dict[str, Any],
) -> dict[str, str]:
    """Channel Talk UserChat 이벤트 payload에서 Agent 초기 입력을 생성
    """
    channel_id, user_chat_id = extract_channel_talk_user_chat_ids(payload)
    if not channel_id or not user_chat_id:
        return {}

    record = load_channel_talk_connection(channel_id=channel_id)
    if record is None:
        raise ValueError("channel_talk credentials not found")

    contextual_content = await fetch_channel_talk_user_chat_context(
        connection_record=record,
        user_chat_id=user_chat_id,
    )
    return {
        CHANNEL_TALK_CHANNEL_ID_KEY: channel_id,
        CHANNEL_TALK_USER_CHAT_ID_KEY: user_chat_id,
        CHANNEL_TALK_USER_CHAT_CONTEXT_KEY: contextual_content,
    }


def extract_channel_talk_user_chat_ids(payload: dict[str, Any]) -> tuple[str, str]:
    entity = payload.get("entity")
    if not isinstance(entity, dict):
        return "", ""

    channel_id = str(entity.get("channelId") or "").strip()
    if not channel_id:
        return "", ""

    user_chat_id = ""
    if entity.get("chatType") == "userChat":
        user_chat_id = str(entity.get("chatId") or "").strip()
    if not user_chat_id:
        user_chat_id = str(entity.get("id") or "").strip()
    return channel_id, user_chat_id


async def fetch_channel_talk_user_chat_context(
    *,
    connection_record: ChannelTalkCredentialsRecord,
    user_chat_id: str,
    fetcher: ChannelTalkUserChatFullSyncFetcher | None = None,
    transformer: UserChatTransformer | None = None,
) -> str:
    connection = ChannelTalkUserChatFullSyncConnection.from_credentials_record(
        connection_record
    )
    fetcher = fetcher or ChannelTalkUserChatFullSyncFetcher()
    transformer = transformer or UserChatTransformer()
    now = datetime.now(timezone.utc)
    sync_window = SyncWindow(window_start=now, window_end=now)

    bundle = await fetcher.fetch_user_chat_bundle_by_id(
        connection=connection,
        user_chat_id=user_chat_id,
    )
    managers_by_id = await fetcher.fetch_managers_by_id(connection=connection)
    document = transformer.build(
        execution=connection,
        sync_window=sync_window,
        bundle=bundle,
        managers_by_id=managers_by_id,
    )
    return document.contextual_content
