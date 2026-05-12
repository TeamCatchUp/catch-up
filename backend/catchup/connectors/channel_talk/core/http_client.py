from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
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
from catchup.connectors.channel_talk.core.rate_limiter import (
    ChannelTalkCoreBucketRateLimiter,
)
from catchup.connectors.channel_talk.core.rate_limiter import (
    get_channel_talk_core_rate_limiter,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.http_helpers import decode_response_json
from catchup.connectors.channel_talk.http_helpers import extract_response_error_metadata
from catchup.connectors.channel_talk.http_helpers import is_success_response
from catchup.utils.client import get_global_async_client

logger = structlog.get_logger(__name__)

RequestParams = dict[str, Any] | list[tuple[str, str]]


class ChannelTalkCoreRateLimiterGetter(Protocol):
    def __call__(
        self,
        *,
        channel_id: str,
        method: str,
        path: str,
    ) -> Awaitable[ChannelTalkCoreBucketRateLimiter]: ...


@dataclass(frozen=True)
class _RateLimitRetryDelay:
    seconds: int
    source: str


class ChannelTalkCoreHttpClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        rate_limiter_getter: ChannelTalkCoreRateLimiterGetter | None = None,
        max_rate_limit_retries: int | None = None,
        max_rate_limit_wait_seconds: int | None = None,
        clock: Callable[[], float] = time,
    ) -> None:
        default_base_url = getattr(
            settings,
            "CHANNEL_TALK_API_URL",
            "https://api.channel.io",
        )
        default_timeout = getattr(settings, "CHANNEL_TALK_API_TIMEOUT_SECONDS", 10.0)

        self.base_url = str(base_url or default_base_url).rstrip("/")
        self.timeout_seconds = float(timeout_seconds or default_timeout)
        self._http_client = http_client or get_global_async_client()
        self._sleep = sleep or asyncio.sleep
        self._rate_limiter_getter = (
            rate_limiter_getter or get_channel_talk_core_rate_limiter
        )
        self._max_rate_limit_retries = max(
            0,
            int(
                max_rate_limit_retries
                if max_rate_limit_retries is not None
                else settings.CHANNEL_TALK_CORE_API_MAX_RETRY_ATTEMPTS
            ),
        )
        self._max_rate_limit_wait_seconds = max(
            1,
            int(
                max_rate_limit_wait_seconds
                if max_rate_limit_wait_seconds is not None
                else settings.CHANNEL_TALK_CORE_API_MAX_WAIT_SECONDS_PER_CALL
            ),
        )
        self._clock = clock

    async def request_json(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: RequestParams | None = None,
        channel_id: str | None = None,
    ) -> Any:
        response = await self.send(
            method=method,
            path=path,
            headers=headers,
            params=params,
            channel_id=channel_id,
        )
        return self.decode_response(response)

    async def send(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: RequestParams | None = None,
        channel_id: str | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        limiter = await self._resolve_rate_limiter(
            channel_id=channel_id,
            method=method,
            path=path,
        )

        for retry_attempt in range(self._max_rate_limit_retries + 1):
            await self._wait_for_rate_limit_slot(limiter)
            response = await self._perform_request(
                method=method,
                url=url,
                headers=headers,
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
                channel_id=channel_id,
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
                error_message="Channel Talk returned a non-JSON response",
            )

        raise self._build_response_error(response)

    async def _perform_request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: RequestParams | None,
    ) -> httpx.Response:
        try:
            return await self._http_client.request(
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

    async def _resolve_rate_limiter(
        self,
        *,
        channel_id: str | None,
        method: str,
        path: str,
    ) -> ChannelTalkCoreBucketRateLimiter | None:
        normalized_channel_id = str(channel_id or "").strip()
        if not normalized_channel_id:
            return None

        return await self._rate_limiter_getter(
            channel_id=normalized_channel_id,
            method=method,
            path=path,
        )

    async def _wait_for_rate_limit_slot(
        self,
        limiter: ChannelTalkCoreBucketRateLimiter | None,
    ) -> None:
        if limiter is None:
            return

        delay = await limiter.acquire_delay()
        if delay > 0:
            await self._sleep(delay)

    async def _defer_rate_limiter(
        self,
        limiter: ChannelTalkCoreBucketRateLimiter | None,
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
        channel_id: str | None,
        method: str,
        path: str,
        retry_attempt: int,
        retry_delay: _RateLimitRetryDelay,
    ) -> None:
        logger.warning(
            "channel_talk_api_rate_limited",
            channel_id=channel_id,
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
                _extract_upstream_error_message(
                    metadata,
                    fallback="Channel Talk credentials are invalid or unauthorized",
                ),
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
                _extract_upstream_error_message(
                    metadata,
                    fallback="Channel Talk rejected the request",
                ),
                metadata=metadata,
            )
        if status_code >= 500:
            return ChannelTalkUpstreamError(
                _extract_upstream_error_message(
                    metadata,
                    fallback=(
                        "Channel Talk API request failed with "
                        f"upstream status {status_code}"
                    ),
                ),
                status_code=status_code,
                metadata=metadata,
            )
        return ChannelTalkUpstreamError(
            _extract_upstream_error_message(
                metadata,
                fallback="Channel Talk API request failed",
            ),
            status_code=status_code,
            metadata=metadata,
        )


def _extract_upstream_error_message(
    metadata: dict[str, Any],
    *,
    fallback: str,
) -> str:
    body = metadata.get("body")
    if isinstance(body, str):
        return body.strip() or fallback
    if body is None:
        return fallback
    if isinstance(body, dict):
        message = _find_error_message(body)
        if message:
            return message
    return json.dumps(body, ensure_ascii=False, default=str)


def _find_error_message(body: dict[str, Any]) -> str | None:
    message = body.get("message")
    if message is not None and str(message).strip():
        return str(message)

    error = body.get("error")
    if isinstance(error, dict):
        nested_message = error.get("message")
        if nested_message is not None and str(nested_message).strip():
            return str(nested_message)
    if error is not None and str(error).strip():
        return str(error)
    return None
