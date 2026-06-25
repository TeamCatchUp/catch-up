from __future__ import annotations

import asyncio

from pydantic import BaseModel
from pydantic import ConfigDict

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.core.user_chat_fetch_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)


class ChannelTalkUserChatOriginalPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: ChannelTalkUserChatDetail | None = None
    messages: tuple[ChannelTalkUserChatMessage, ...] = ()
    next_cursor: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        detail: ChannelTalkUserChatDetail | None,
        messages: tuple[ChannelTalkUserChatMessage, ...],
        next_cursor: str | None,
    ) -> "ChannelTalkUserChatOriginalPage":
        return cls(
            detail=detail,
            messages=messages,
            next_cursor=next_cursor,
        )


class ChannelTalkUserChatOriginalFetcher:
    def __init__(
        self,
        *,
        client: ChannelTalkCoreApiClient | None = None,
        default_limit: int = 500,
    ) -> None:
        if default_limit < 1:
            raise ValueError("default_limit must be positive")
        self.client = client or ChannelTalkCoreApiClient()
        self._default_limit = default_limit

    async def fetch_user_chat_original_page(
        self,
        *,
        connection: ChannelTalkUserChatFullSyncConnection,
        user_chat_id: str,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> ChannelTalkUserChatOriginalPage:
        resolved_limit = self._default_limit if limit is None else limit
        if resolved_limit < 1:
            raise ValueError("limit must be positive")

        detail, page = await asyncio.gather(
            self.client.get_user_chat(
                access_key=connection.access_key,
                access_secret=connection.access_secret,
                channel_id=connection.channel_id,
                user_chat_id=user_chat_id,
            ),
            self.client.list_user_chat_messages_page(
                access_key=connection.access_key,
                access_secret=connection.access_secret,
                channel_id=connection.channel_id,
                user_chat_id=user_chat_id,
                cursor=cursor,
                limit=resolved_limit,
                sort_order="asc",
            ),
        )
        return ChannelTalkUserChatOriginalPage.from_values(
            detail=detail,
            messages=tuple(page.messages),
            next_cursor=page.next_cursor,
        )
