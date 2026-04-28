from __future__ import annotations

import base64
from collections.abc import Buffer
from typing import Any
from typing import Callable
from typing import TypeVar

import httpx
import structlog

from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.channel_talk.documents_schemas import (
    ChannelTalkDocumentAuthorPage,
)
from catchup.connectors.channel_talk.documents_schemas import (
    ChannelTalkDocumentNavNodePage,
)
from catchup.connectors.channel_talk.documents_schemas import ChannelTalkDocumentSpace
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.utils.client import get_global_async_client

logger = structlog.get_logger(__name__)

ParsedPayloadT = TypeVar("ParsedPayloadT")


# noinspection DuplicatedCode
class ChannelTalkDocumentsApiClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        default_base_url = getattr(
            settings,
            "CHANNEL_TALK_DOCUMENTS_API_URL",
            "https://document-api.channel.io",
        )
        default_timeout = getattr(settings, "CHANNEL_TALK_API_TIMEOUT_SECONDS", 10.0)

        self.base_url = str(base_url or default_base_url).rstrip("/")
        self.timeout_seconds = float(timeout_seconds or default_timeout)
        self._http_client = http_client or get_global_async_client()

    async def get_current_space(
        self,
        access_key: str,
        access_secret: str,
    ) -> ChannelTalkDocumentSpace:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
        )
        return self._parse_payload(
            payload,
            parser=ChannelTalkDocumentSpace.from_api_payload,
            log_event="channel_talk_documents_invalid_space_payload",
            error_message="Channel Talk Documents returned an invalid space payload",
        )

    async def list_authors(
        self,
        access_key: str,
        access_secret: str,
        *,
        since: str | None = None,
        limit: int = 100,
    ) -> ChannelTalkDocumentAuthorPage:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me/authors",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
            params=self._build_list_params(since=since, limit=limit),
        )
        return self._parse_payload(
            payload,
            parser=ChannelTalkDocumentAuthorPage.from_api_payload,
            log_event="channel_talk_documents_invalid_author_list_payload",
            error_message="Channel Talk Documents returned an invalid author list payload",
        )

    async def list_nav_nodes(
        self,
        access_key: str,
        access_secret: str,
    ) -> ChannelTalkDocumentNavNodePage:
        payload = await self._request(
            method="GET",
            path="/open/v1/spaces/$me/nav-nodes/$all",
            headers=self._build_headers(
                access_key=access_key,
                access_secret=access_secret,
            ),
        )
        return self._parse_payload(
            payload,
            parser=ChannelTalkDocumentNavNodePage.from_api_payload,
            log_event="channel_talk_documents_invalid_nav_node_payload",
            error_message="Channel Talk Documents returned an invalid navigation payload",
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
            raise ChannelTalkValidationError("Channel Talk Documents credentials are required")
        credentials: Buffer = f"{normalized_access_key}:{normalized_access_secret}".encode(
            "utf-8"
        )
        token = base64.b64encode(credentials).decode("ascii")
        return {
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
        }

    @staticmethod
    def _build_list_params(
        *,
        since: str | None,
        limit: int,
    ) -> dict[str, Any]:
        normalized_limit = min(max(int(limit), 1), 500)
        params: dict[str, Any] = {"limit": normalized_limit}
        if since is not None and str(since).strip():
            params["since"] = str(since).strip()
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
            return await self._http_client.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning("channel_talk_documents_request_timed_out", url=url)
            raise ChannelTalkTimeoutError(
                "Channel Talk Documents API request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("channel_talk_documents_request_failed", url=url)
            raise ChannelTalkUpstreamError(
                "Failed to reach Channel Talk Documents API",
                metadata={"reason": str(exc)},
            ) from exc

    def _decode_response(self, response: httpx.Response) -> Any:
        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except ValueError as exc:
                raise ChannelTalkPayloadError(
                    "Channel Talk Documents returned a non-JSON response"
                ) from exc

        metadata = self._extract_error_metadata(response)
        status_code = response.status_code
        if status_code in (401, 403):
            raise ChannelTalkAuthenticationError(
                "Channel Talk Documents credentials are invalid or unauthorized",
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
                "Channel Talk Documents rejected the request",
                metadata=metadata,
            )
        if status_code >= 500:
            raise ChannelTalkUpstreamError(
                "Channel Talk Documents API is temporarily unavailable",
                status_code=status_code,
                metadata=metadata,
            )
        raise ChannelTalkUpstreamError(
            "Channel Talk Documents API request failed",
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

    @staticmethod
    def _parse_payload(
        payload: Any,
        *,
        parser: Callable[[Any], ParsedPayloadT],
        log_event: str,
        error_message: str,
    ) -> ParsedPayloadT:
        try:
            return parser(payload)
        except ValueError as exc:
            logger.exception(log_event)
            raise ChannelTalkPayloadError(error_message) from exc
