from __future__ import annotations

from typing import Any

import httpx
import structlog

from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.http_helpers import build_since_limit_params
from catchup.connectors.channel_talk.http_helpers import decode_response_json
from catchup.connectors.channel_talk.http_helpers import extract_response_error_metadata
from catchup.connectors.channel_talk.http_helpers import is_success_response
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
from catchup.utils.client import get_global_async_client

logger = structlog.get_logger(__name__)


class ChannelTalkCoreApiClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        default_base_url = getattr(
            settings, "CHANNEL_TALK_API_URL", "https://api.channel.io"
        )
        default_timeout = getattr(settings, "CHANNEL_TALK_API_TIMEOUT_SECONDS", 10.0)

        self.base_url = str(base_url or default_base_url).rstrip("/")
        self.timeout_seconds = float(timeout_seconds or default_timeout)
        self._http_client = http_client or get_global_async_client()

    async def get_current_channel(
        self,
        access_key: str,
        access_secret: str,
    ) -> ChannelTalkCurrentChannel:
        payload = await self._request(
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
        since: str | None = None,
        limit: int = 500,
    ) -> ChannelTalkManagerMetadataPage:
        payload = await self._request(
            method="GET",
            path="/open/v5/managers",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            params=build_since_limit_params(since=since, limit=limit),
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
        payload = await self._request(
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
        state: ChannelTalkUserChatState | str,
        since: str | None = None,
        limit: int = 500,
        sort_order: str | None = "desc",
    ) -> ChannelTalkUserChatListPage:
        resolved_state = ChannelTalkUserChatState(str(state).strip().lower())
        response = await self._send_request(
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
        )
        payload = self._decode_response(response)
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
        user_chat_id: str,
    ) -> ChannelTalkUserChatDetail:
        resolved_user_chat_id = _require_user_chat_id(user_chat_id)
        payload = await self._request(
            method="GET",
            path=f"/open/v5/user-chats/{resolved_user_chat_id}",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
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
        user_chat_id: str,
        since: str | None = None,
        limit: int = 500,
        sort_order: str | None = "desc",
    ) -> ChannelTalkUserChatMessagePage:
        resolved_user_chat_id = _require_user_chat_id(user_chat_id)
        response = await self._send_request(
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
        )
        payload = self._decode_response(response)
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

    async def _request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._send_request(
            method=method,
            path=path,
            headers=headers,
            params=params,
        )

        return self._decode_response(response)

    async def _send_request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            response = await self._http_client.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning("channel_talk_request_timed_out", url=url)
            raise ChannelTalkTimeoutError("Channel Talk API request timed out") from exc
        except httpx.HTTPError as exc:
            logger.exception("channel_talk_request_failed", url=url)
            raise ChannelTalkUpstreamError(
                "Failed to reach Channel Talk API",
                metadata={"reason": str(exc)},
            ) from exc

        return response

    def _decode_response(self, response: httpx.Response) -> Any:
        if is_success_response(response):
            return decode_response_json(
                response,
                error_message="Channel Talk returned a non-JSON response",
            )

        raise self._build_response_error(response)

    @staticmethod
    def _build_response_error(response: httpx.Response) -> Exception:
        metadata = extract_response_error_metadata(response)
        status_code = response.status_code
        if status_code in (401, 403):
            return ChannelTalkAuthenticationError(
                "Channel Talk credentials are invalid or unauthorized",
                metadata=metadata,
            )
        if status_code == 429:
            return ChannelTalkRateLimitError(
                retry_after=parse_retry_after_header(
                    response.headers.get("Retry-After"),
                    default=60,
                ),
                metadata=metadata,
            )
        if status_code == 400:
            return ChannelTalkValidationError(
                "Channel Talk rejected the request",
                metadata=metadata,
            )
        if status_code >= 500:
            return ChannelTalkUpstreamError(
                "Channel Talk API is temporarily unavailable",
                status_code=status_code,
                metadata=metadata,
            )
        return ChannelTalkUpstreamError(
            "Channel Talk API request failed",
            status_code=status_code,
            metadata=metadata,
        )


def _require_user_chat_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ChannelTalkValidationError("user_chat_id is required")
    return text


def _normalize_sort_order(value: str | None) -> str:
    return str(value or "").strip() or "desc"
