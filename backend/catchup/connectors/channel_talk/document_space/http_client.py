from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable
from collections.abc import Buffer
from collections.abc import Callable
from dataclasses import dataclass
from time import time
from typing import Any
from typing import Protocol

import httpx
import structlog

from catchup.configs.config import settings
from catchup.connectors.base.retry import parse_reset_timestamp_header
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.channel_talk.document_space.rate_limiter import (
    ChannelTalkDocumentSpaceRateLimiter,
)
from catchup.connectors.channel_talk.document_space.rate_limiter import (
    get_channel_talk_document_space_rate_limiter,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.http_helpers import build_upstream_error_message
from catchup.connectors.channel_talk.http_helpers import decode_response_json
from catchup.connectors.channel_talk.http_helpers import extract_response_error_metadata
from catchup.connectors.channel_talk.http_helpers import is_success_response
from catchup.utils.client import get_global_async_client

logger = structlog.get_logger(__name__)

RequestParams = dict[str, Any] | list[tuple[str, str]]


class ChannelTalkDocumentSpaceRateLimiterGetter(Protocol):
    def __call__(
        self,
        *,
        space_id: str,
    ) -> Awaitable[ChannelTalkDocumentSpaceRateLimiter]: ...


@dataclass(frozen=True)
class _RateLimitRetryDelay:
    seconds: int
    source: str


class ChannelTalkDocumentsHttpClient:
    def __init__(
        self,
        *,
        access_key: str,
        access_secret: str,
        space_id: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        rate_limiter_getter: ChannelTalkDocumentSpaceRateLimiterGetter | None = None,
        max_rate_limit_retries: int | None = None,
        max_rate_limit_wait_seconds: int | None = None,
        clock: Callable[[], float] = time,
    ) -> None:
        default_base_url = getattr(
            settings,
            "CHANNEL_TALK_DOCUMENTS_API_URL",
            "https://document-api.channel.io",
        )
        default_timeout = getattr(settings, "CHANNEL_TALK_API_TIMEOUT_SECONDS", 10.0)

        self.base_url = str(base_url or default_base_url).rstrip("/")
        self.timeout_seconds = float(timeout_seconds or default_timeout)
        self.space_id = _normalize_optional_space_id(space_id)
        self._http_client = http_client or get_global_async_client()
        self._sleep = sleep or asyncio.sleep
        self._rate_limiter_getter = (
            rate_limiter_getter or get_channel_talk_document_space_rate_limiter
        )
        self._max_rate_limit_retries = max(
            0,
            int(
                max_rate_limit_retries
                if max_rate_limit_retries is not None
                else settings.CHANNEL_TALK_DOCUMENTS_API_MAX_RETRY_ATTEMPTS
            ),
        )
        self._max_rate_limit_wait_seconds = max(
            1,
            int(
                max_rate_limit_wait_seconds
                if max_rate_limit_wait_seconds is not None
                else settings.CHANNEL_TALK_DOCUMENTS_API_MAX_WAIT_SECONDS_PER_CALL
            ),
        )
        self._clock = clock
        self._headers = _build_headers(
            access_key=access_key,
            access_secret=access_secret,
        )

    async def request_json(
        self,
        *,
        method: str,
        path: str,
        params: RequestParams | None = None,
    ) -> Any:
        response = await self.send(
            method=method,
            path=path,
            params=params,
        )
        return self.decode_response(response)

    async def send(
        self,
        *,
        method: str,
        path: str,
        params: RequestParams | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        limiter = await self._resolve_rate_limiter()

        for retry_attempt in range(self._max_rate_limit_retries + 1):
            await self._wait_for_rate_limit_slot(limiter)
            response = await self._perform_request(
                method=method,
                url=url,
                params=params,
            )
            if response.status_code != 429:
                return response

            retry_delay = self._resolve_rate_limit_retry_delay(
                response,
                default=1,
            )
            await self._defer_rate_limiter(limiter, retry_delay)
            if not self._can_retry_rate_limit(
                retry_attempt=retry_attempt,
                retry_delay=retry_delay,
            ):
                return response

            self._log_rate_limit_retry(
                method=method,
                path=path,
                retry_attempt=retry_attempt + 1,
                retry_delay=retry_delay,
            )
            await self._sleep(retry_delay.seconds)

        return response

    def decode_response(self, response: httpx.Response) -> Any:
        if is_success_response(response):
            return decode_response_json(
                response,
                error_message="Channel Talk Documents returned a non-JSON response",
            )

        raise self._build_response_error(response)

    async def _perform_request(
        self,
        *,
        method: str,
        url: str,
        params: RequestParams | None,
    ) -> httpx.Response:
        try:
            return await self._http_client.request(
                method,
                url,
                headers=self._headers,
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

    async def _resolve_rate_limiter(
        self,
    ) -> ChannelTalkDocumentSpaceRateLimiter | None:
        if self.space_id is None:
            return None

        return await self._rate_limiter_getter(space_id=self.space_id)

    async def _wait_for_rate_limit_slot(
        self,
        limiter: ChannelTalkDocumentSpaceRateLimiter | None,
    ) -> None:
        if limiter is None:
            return

        delay = await limiter.acquire_delay()
        if delay > 0:
            await self._sleep(delay)

    async def _defer_rate_limiter(
        self,
        limiter: ChannelTalkDocumentSpaceRateLimiter | None,
        retry_delay: _RateLimitRetryDelay,
    ) -> None:
        if limiter is not None:
            await limiter.defer_for(retry_delay.seconds)

    def _can_retry_rate_limit(
        self,
        *,
        retry_attempt: int,
        retry_delay: _RateLimitRetryDelay,
    ) -> bool:
        return (
            retry_attempt < self._max_rate_limit_retries
            and retry_delay.seconds <= self._max_rate_limit_wait_seconds
        )

    def _resolve_rate_limit_retry_delay(
        self,
        response: httpx.Response,
        *,
        default: int,
    ) -> _RateLimitRetryDelay:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None and retry_after.strip():
            return _RateLimitRetryDelay(
                seconds=parse_retry_after_header(retry_after, default=default),
                source="retry-after",
            )

        reset = response.headers.get("x-ratelimit-reset") or response.headers.get(
            "x-rate-limit-reset"
        )
        if reset is not None and reset.strip():
            return _RateLimitRetryDelay(
                seconds=parse_reset_timestamp_header(
                    reset,
                    now_ts=int(self._clock()),
                    default=default,
                ),
                source="x-ratelimit-reset",
            )

        return _RateLimitRetryDelay(seconds=max(1, int(default)), source="default")

    def _log_rate_limit_retry(
        self,
        *,
        method: str,
        path: str,
        retry_attempt: int,
        retry_delay: _RateLimitRetryDelay,
    ) -> None:
        logger.warning(
            "channel_talk_documents_api_rate_limited",
            space_id=self.space_id,
            method=method,
            path=path,
            retry_attempt=retry_attempt,
            retry_after=retry_delay.seconds,
            retry_after_source=retry_delay.source,
        )

    def _build_response_error(self, response: httpx.Response) -> Exception:
        metadata = extract_response_error_metadata(response)
        status_code = response.status_code
        if status_code in (401, 403):
            return ChannelTalkAuthenticationError(
                "Channel Talk Documents credentials are invalid or unauthorized",
                metadata=metadata,
            )
        if status_code == 429:
            return ChannelTalkRateLimitError(
                retry_after=self._resolve_rate_limit_retry_delay(
                    response,
                    default=60,
                ).seconds,
                metadata=metadata,
            )
        if status_code == 400:
            return ChannelTalkValidationError(
                "Channel Talk Documents rejected the request",
                metadata=metadata,
            )
        if status_code >= 500:
            return ChannelTalkUpstreamError(
                build_upstream_error_message(
                    service_name="Channel Talk Documents API",
                    status_code=status_code,
                    metadata=metadata,
                ),
                status_code=status_code,
                metadata=metadata,
            )
        return ChannelTalkUpstreamError(
            "Channel Talk Documents API request failed",
            status_code=status_code,
            metadata=metadata,
        )


def _build_headers(
    *,
    access_key: str,
    access_secret: str,
) -> dict[str, str]:
    normalized_access_key = str(access_key or "").strip()
    normalized_access_secret = str(access_secret or "").strip()
    if not normalized_access_key or not normalized_access_secret:
        raise ChannelTalkValidationError(
            "Channel Talk Documents credentials are required"
        )
    credentials: Buffer = (
        f"{normalized_access_key}:{normalized_access_secret}".encode("utf-8")
    )
    token = base64.b64encode(credentials).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {token}",
    }


def _normalize_optional_space_id(space_id: str | None) -> str | None:
    if space_id is None:
        return None
    normalized_space_id = str(space_id).strip()
    return normalized_space_id or None
