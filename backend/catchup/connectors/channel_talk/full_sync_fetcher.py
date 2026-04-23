from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatListItem
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessage
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatState
from catchup.utils.validation import require_text


class ChannelTalkFetchedUserChat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ChannelTalkUserChatState
    list_item: ChannelTalkUserChatListItem
    detail: ChannelTalkUserChatDetail
    messages: tuple[ChannelTalkUserChatMessage, ...] = ()

    @field_validator("messages")
    @classmethod
    def _validate_messages(
        cls,
        value: tuple[ChannelTalkUserChatMessage, ...],
    ) -> tuple[ChannelTalkUserChatMessage, ...]:
        return tuple(value)


class ChannelTalkFullSyncFetcher:
    def __init__(
        self,
        *,
        client: ChannelTalkApiClient | None = None,
    ) -> None:
        self.client = client or ChannelTalkApiClient()

    async def fetch_user_chats(
        self,
        *,
        connection: ChannelTalkCredentialsRecord,
        states: tuple[ChannelTalkUserChatState, ...],
        sync_window: FullSyncWindow,
        checkpoint_state: ChannelTalkUserChatState | None = None,
        checkpoint_cursor: str | None = None,
    ) -> tuple[ChannelTalkFetchedUserChat, ...]:
        access_key = require_text(connection.access_key, "access_key")
        access_secret = require_text(connection.access_secret, "access_secret")

        fetched: list[ChannelTalkFetchedUserChat] = []
        resume_from_checkpoint = checkpoint_state is not None

        for state in states:
            if resume_from_checkpoint and checkpoint_state != state:
                continue

            next_cursor = checkpoint_cursor if checkpoint_state == state else None
            resume_from_checkpoint = False

            while True:
                page = await self.client.list_user_chats(
                    access_key=access_key,
                    access_secret=access_secret,
                    state=state,
                    since=next_cursor,
                    sort_order="desc",
                )

                reached_older_window = False
                for item in page.items:
                    if (
                        item.ordering_marker is not None
                        and item.ordering_marker < sync_window.window_start
                    ):
                        reached_older_window = True
                        continue

                    detail = await self.client.get_user_chat(
                        access_key=access_key,
                        access_secret=access_secret,
                        user_chat_id=item.user_chat_id,
                    )
                    messages = await self._list_user_chat_messages(
                        access_key=access_key,
                        access_secret=access_secret,
                        user_chat_id=item.user_chat_id,
                    )
                    fetched.append(
                        ChannelTalkFetchedUserChat(
                            state=state,
                            list_item=item,
                            detail=detail,
                            messages=tuple(messages),
                        )
                    )

                if reached_older_window or page.next_cursor is None:
                    break
                next_cursor = page.next_cursor

        return tuple(fetched)

    async def fetch_managers_by_id(
        self,
        *,
        connection: ChannelTalkCredentialsRecord,
    ) -> dict[str, ChannelTalkManagerMetadata]:
        access_key = require_text(connection.access_key, "access_key")
        access_secret = require_text(connection.access_secret, "access_secret")

        managers_by_id: dict[str, ChannelTalkManagerMetadata] = {}
        next_page_token: str | None = None
        while True:
            page = await self.client.list_managers(
                access_key=access_key,
                access_secret=access_secret,
                since=next_page_token,
            )
            for manager in page.managers:
                managers_by_id[manager.manager_id] = manager
            if page.next_page_token is None:
                return managers_by_id
            next_page_token = page.next_page_token

    async def _list_user_chat_messages(
        self,
        *,
        access_key: str,
        access_secret: str,
        user_chat_id: str,
    ) -> list[ChannelTalkUserChatMessage]:
        messages: list[ChannelTalkUserChatMessage] = []
        next_cursor: str | None = None

        while True:
            page = await self.client.list_user_chat_messages(
                access_key=access_key,
                access_secret=access_secret,
                user_chat_id=user_chat_id,
                since=next_cursor,
                sort_order="asc",
            )
            messages.extend(page.messages)
            if page.next_cursor is None:
                return messages
            next_cursor = page.next_cursor
