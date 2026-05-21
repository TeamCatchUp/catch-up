from __future__ import annotations

from typing import Any

import structlog

from catchup.connectors.channel_talk.core.http_client import ChannelTalkCoreHttpClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.http_helpers import build_since_limit_params
from catchup.connectors.channel_talk.http_helpers import parse_channel_talk_payload
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadataPage,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadataPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessagePage,
)

logger = structlog.get_logger(__name__)


class ChannelTalkCoreApiClient:
    def __init__(
        self,
        *,
        transport: ChannelTalkCoreHttpClient | None = None,
    ) -> None:
        self._transport = transport or ChannelTalkCoreHttpClient()

    async def get_current_channel(
        self,
        access_key: str,
        access_secret: str,
    ) -> ChannelTalkCurrentChannel:
        payload = await self._transport.request_json(
            method="GET",
            path="/open/v5/channel",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkCurrentChannel.from_api_payload,
            log_event="channel_talk_invalid_payload",
            error_message="Channel Talk returned an invalid channel payload",
            logger=logger,
        )

    async def list_managers(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        since: str | None = None,
        limit: int = 500,
    ) -> ChannelTalkManagerMetadataPage:
        payload = await self._transport.request_json(
            method="GET",
            path="/open/v5/managers",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            params=build_since_limit_params(since=since, limit=limit),
            channel_id=channel_id,
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkManagerMetadataPage.from_api_payload,
            log_event="channel_talk_invalid_manager_list_payload",
            error_message="Channel Talk returned an invalid manager list payload",
            logger=logger,
        )

    async def list_groups(
        self,
        access_key: str,
        access_secret: str,
        *,
        since: str | None = None,
        limit: int = 500,
    ) -> ChannelTalkGroupMetadataPage:
        payload = await self._transport.request_json(
            method="GET",
            path="/open/v5/groups",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            params=build_since_limit_params(since=since, limit=limit),
        )
        return parse_channel_talk_payload(
            payload,
            parser=ChannelTalkGroupMetadataPage.from_api_payload,
            log_event="channel_talk_invalid_group_list_payload",
            error_message="Channel Talk returned an invalid group list payload",
            logger=logger,
        )

    async def list_user_chats(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        state: ChannelTalkUserChatState | str,
        since: str | None = None,
        limit: int = 500,
        sort_order: str | None = "desc",
    ) -> ChannelTalkUserChatListPage:
        resolved_state = ChannelTalkUserChatState(str(state).strip().lower())
        response = await self._transport.send(
            method="GET",
            path="/open/v5/user-chats",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            params=self._build_user_chat_list_params(
                state=resolved_state,
                since=since,
                limit=limit,
                sort_order=sort_order,
            ),
            channel_id=channel_id,
        )
        payload = self._transport.decode_response(response)
        return parse_channel_talk_payload(
            payload,
            parser=lambda raw: ChannelTalkUserChatListPage.from_api_payload(
                raw,
                state=resolved_state,
                headers=response.headers,
            ),
            log_event="channel_talk_invalid_user_chat_list_payload",
            error_message="Channel Talk returned an invalid user chat list payload",
            logger=logger,
        )

    async def get_user_chat(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        user_chat_id: str,
    ) -> ChannelTalkUserChatDetail:
        resolved_user_chat_id = _require_user_chat_id(user_chat_id)
        payload = await self._transport.request_json(
            method="GET",
            path=f"/open/v5/user-chats/{resolved_user_chat_id}",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            channel_id=channel_id,
        )
        return parse_channel_talk_payload(
            payload,
            parser=lambda raw: ChannelTalkUserChatDetail.from_api_payload(
                raw,
                user_chat_id=resolved_user_chat_id,
            ),
            log_event="channel_talk_invalid_user_chat_detail_payload",
            error_message="Channel Talk returned an invalid user chat detail payload",
            logger=logger,
        )

    async def list_user_chat_messages(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        user_chat_id: str,
        since: str | None = None,
        limit: int = 500,
        sort_order: str | None = "desc",
    ) -> ChannelTalkUserChatMessagePage:
        resolved_user_chat_id = _require_user_chat_id(user_chat_id)
        response = await self._transport.send(
            method="GET",
            path=f"/open/v5/user-chats/{resolved_user_chat_id}/messages",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            params=self._build_user_chat_message_list_params(
                since=since,
                limit=limit,
                sort_order=sort_order,
            ),
            channel_id=channel_id,
        )
        payload = self._transport.decode_response(response)
        return parse_channel_talk_payload(
            payload,
            parser=lambda raw: ChannelTalkUserChatMessagePage.from_api_payload(
                raw,
                user_chat_id=resolved_user_chat_id,
                headers=response.headers,
            ),
            log_event="channel_talk_invalid_user_chat_message_list_payload",
            error_message="Channel Talk returned an invalid user chat message list payload",
            logger=logger,
        )

    async def list_user_chat_messages_page(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        user_chat_id: str,
        cursor: str | None = None,
        limit: int = 500,
        sort_order: str | None = "asc",
    ) -> ChannelTalkUserChatMessagePage:
        return await self.list_user_chat_messages(
            access_key=access_key,
            access_secret=access_secret,
            channel_id=channel_id,
            user_chat_id=user_chat_id,
            since=cursor,
            limit=limit,
            sort_order=sort_order,
        )

    @staticmethod
    def _build_headers(
        *,
        access_key: str,
        access_secret: str,
    ) -> dict[str, str]:
        normalized_access_key = str(access_key or "").strip()
        normalized_access_secret = str(access_secret or "").strip()
        if not normalized_access_key or not normalized_access_secret:
            raise ChannelTalkValidationError("Channel Talk credentials are required")

        return {
            "Accept": "application/json",
            "x-access-key": normalized_access_key,
            "x-access-secret": normalized_access_secret,
        }

    def _build_user_chat_list_params(
        self,
        *,
        state: ChannelTalkUserChatState,
        since: str | None,
        limit: int,
        sort_order: str | None,
    ) -> dict[str, Any]:
        params = build_since_limit_params(
            since=since,
            limit=limit,
        )
        params["state"] = str(state).strip()
        params["sortOrder"] = _normalize_sort_order(sort_order)
        return params

    def _build_user_chat_message_list_params(
        self,
        *,
        since: str | None,
        limit: int,
        sort_order: str | None,
    ) -> dict[str, Any]:
        params = build_since_limit_params(
            since=since,
            limit=limit,
        )
        params["sortOrder"] = _normalize_sort_order(sort_order)
        return params


def _require_user_chat_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ChannelTalkValidationError("user_chat_id is required")
    return text


def _normalize_sort_order(value: str | None) -> str:
    return str(value or "").strip() or "desc"
