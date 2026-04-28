from __future__ import annotations

import asyncio

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.core_api_client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.utils.validation import require_text


class ChannelTalkFullSyncConnection(BaseModel):
    """Full-sync fetch boundary에서 사용하는 validated Channel Talk credentials."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    access_key: str
    access_secret: str

    @field_validator("channel_id", "access_key", "access_secret")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @classmethod
    def from_credentials_record(
        cls,
        record: ChannelTalkCredentialsRecord,
    ) -> "ChannelTalkFullSyncConnection":
        return cls(
            channel_id=record.channel_id,
            access_key=require_text(record.access_key, "access_key"),
            access_secret=require_text(record.access_secret, "access_secret"),
        )


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


class ChannelTalkFetchedUserChatsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundles: tuple[ChannelTalkFetchedUserChat, ...] = ()
    next_checkpoint_state: ChannelTalkUserChatState | None = None
    next_checkpoint_cursor: str | None = None

    @model_validator(mode="after")
    def _validate_checkpoint_shape(self) -> "ChannelTalkFetchedUserChatsResult":
        if (
            self.next_checkpoint_cursor is not None
            and self.next_checkpoint_state is None
        ):
            raise ValueError(
                "next_checkpoint_state is required with next_checkpoint_cursor"
            )
        return self


class ChannelTalkFullSyncFetcher:
    def __init__(
        self,
        *,
        client: ChannelTalkCoreApiClient | None = None,
        max_concurrent_user_chat_fetches: int = 5,
        max_user_chat_pages_per_run: int | None = None,
    ) -> None:
        if max_concurrent_user_chat_fetches < 1:
            raise ValueError("max_concurrent_user_chat_fetches must be positive")
        if max_user_chat_pages_per_run is not None and max_user_chat_pages_per_run < 1:
            raise ValueError("max_user_chat_pages_per_run must be positive")
        self.client = client or ChannelTalkCoreApiClient()
        self._max_concurrent_user_chat_fetches = max_concurrent_user_chat_fetches
        self._max_user_chat_pages_per_run = max_user_chat_pages_per_run

    async def fetch_user_chats(
        self,
        *,
        connection: ChannelTalkFullSyncConnection,
        states: tuple[ChannelTalkUserChatState, ...],
        sync_window: FullSyncWindow,
        checkpoint_state: ChannelTalkUserChatState | None = None,
        checkpoint_cursor: str | None = None,
    ) -> ChannelTalkFetchedUserChatsResult:
        access_key = connection.access_key
        access_secret = connection.access_secret

        fetched: list[ChannelTalkFetchedUserChat] = []
        resume_from_checkpoint = checkpoint_state is not None
        fetched_pages = 0

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
                fetched_pages += 1

                reached_older_window = False
                page_items: list[ChannelTalkUserChatListItem] = []
                for item in page.items:
                    if (
                        item.ordering_marker is not None
                        and item.ordering_marker > sync_window.window_end
                    ):
                        continue
                    if (
                        item.ordering_marker is not None
                        and item.ordering_marker < sync_window.window_start
                    ):
                        reached_older_window = True
                        break

                    page_items.append(item)

                if page_items:
                    semaphore = asyncio.Semaphore(
                        self._max_concurrent_user_chat_fetches
                    )
                    fetched.extend(
                        await asyncio.gather(
                            *(
                                self._fetch_user_chat_bundle(
                                    access_key=access_key,
                                    access_secret=access_secret,
                                    state=state,
                                    item=item,
                                    semaphore=semaphore,
                                )
                                for item in page_items
                            )
                        )
                    )

                if self._reached_page_budget(fetched_pages):
                    if not reached_older_window and page.next_cursor is not None:
                        return ChannelTalkFetchedUserChatsResult(
                            bundles=tuple(fetched),
                            next_checkpoint_state=state,
                            next_checkpoint_cursor=page.next_cursor,
                        )

                    next_state = self._next_state(states=states, current=state)
                    if next_state is not None:
                        return ChannelTalkFetchedUserChatsResult(
                            bundles=tuple(fetched),
                            next_checkpoint_state=next_state,
                        )

                if reached_older_window or page.next_cursor is None:
                    break
                next_cursor = page.next_cursor

        return ChannelTalkFetchedUserChatsResult(bundles=tuple(fetched))

    def _reached_page_budget(self, fetched_pages: int) -> bool:
        return (
            self._max_user_chat_pages_per_run is not None
            and fetched_pages >= self._max_user_chat_pages_per_run
        )

    @staticmethod
    def _next_state(
        *,
        states: tuple[ChannelTalkUserChatState, ...],
        current: ChannelTalkUserChatState,
    ) -> ChannelTalkUserChatState | None:
        for index, state in enumerate(states):
            if state != current:
                continue
            if index + 1 >= len(states):
                return None
            return states[index + 1]
        return None

    async def _fetch_user_chat_bundle(
        self,
        *,
        access_key: str,
        access_secret: str,
        state: ChannelTalkUserChatState,
        item: ChannelTalkUserChatListItem,
        semaphore: asyncio.Semaphore,
    ) -> ChannelTalkFetchedUserChat:
        async with semaphore:
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
        return ChannelTalkFetchedUserChat(
            state=state,
            list_item=item,
            detail=detail,
            messages=tuple(messages),
        )

    async def fetch_managers_by_id(
        self,
        *,
        connection: ChannelTalkFullSyncConnection,
    ) -> dict[str, ChannelTalkManagerMetadata]:
        access_key = connection.access_key
        access_secret = connection.access_secret

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
