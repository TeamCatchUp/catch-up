from __future__ import annotations

import logging
from typing import Any

import httpx

from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas import ChannelTalkCurrentChannel
from catchup.utils.client import get_global_async_client

logger = logging.getLogger(__name__)


class ChannelTalkApiClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        default_base_url = getattr(settings, "CHANNEL_TALK_API_URL", "https://api.channel.io")
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

        try:
            return ChannelTalkCurrentChannel.from_api_payload(payload)
        except ValueError as exc:
            logger.error("channel_talk_invalid_payload", exc_info=True)
            raise ChannelTalkPayloadError("Channel Talk returned an invalid channel payload") from exc

    def _build_headers(
        self,
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

    async def _request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = await self._http_client.request(
                method,
                url,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning("channel_talk_request_timed_out", url=url)
            raise ChannelTalkTimeoutError("Channel Talk API request timed out") from exc
        except httpx.HTTPError as exc:
            logger.error("channel_talk_request_failed", url=url, exc_info=True)
            raise ChannelTalkUpstreamError(
                "Failed to reach Channel Talk API",
                metadata={"reason": str(exc)},
            ) from exc

        return self._decode_response(response)

    def _decode_response(self, response: httpx.Response) -> Any:
        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except ValueError as exc:
                raise ChannelTalkPayloadError("Channel Talk returned a non-JSON response") from exc

        metadata = self._extract_error_metadata(response)
        status_code = response.status_code
        if status_code in (401, 403):
            raise ChannelTalkAuthenticationError(
                "Channel Talk credentials are invalid or unauthorized",
                metadata=metadata,
            )

        if status_code == 429:
            raise ChannelTalkRateLimitError(
                retry_after=parse_retry_after_header(
                    response.headers.get("Retry-After"),
                    default=60,
                ),
                metadata=metadata,
            )

        if status_code == 400:
            raise ChannelTalkValidationError(
                "Channel Talk rejected the request",
                metadata=metadata,
            )

        if status_code >= 500:
            raise ChannelTalkUpstreamError(
                "Channel Talk API is temporarily unavailable",
                status_code=status_code,
                metadata=metadata,
            )

        raise ChannelTalkUpstreamError(
            "Channel Talk API request failed",
            status_code=status_code,
            metadata=metadata,
        )

    @staticmethod
    def _extract_error_metadata(response: httpx.Response) -> dict[str, Any]:
        request_id = (
            response.headers.get("x-request-id")
            or response.headers.get("x-correlation-id")
        )

        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500].strip() or None

        metadata: dict[str, Any] = {"status_code": response.status_code}
        if request_id:
            metadata["request_id"] = request_id
        if body is not None:
            metadata["body"] = body
        return metadata
