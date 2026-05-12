from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import StrEnum
from time import monotonic
from urllib.parse import urlsplit

from catchup.configs.config import settings

CHANNEL_TALK_CORE_API_DOCUMENTED_REFILL_RPS = 10.0


class ChannelTalkCoreRateLimitBucket(StrEnum):
    USER_CHAT_LIST = "user_chat_list"
    CORE_DEFAULT = "core_default"


class ChannelTalkCoreBucketRateLimiter:
    def __init__(
        self,
        *,
        requests_per_second: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        rps = float(requests_per_second)
        if rps <= 0:
            raise ValueError("requests_per_second must be positive")

        self._interval_seconds = 1.0 / min(
            rps,
            CHANNEL_TALK_CORE_API_DOCUMENTED_REFILL_RPS,
        )
        self._next_slot_at = 0.0
        self._clock = clock
        self._lock = asyncio.Lock()

    async def acquire_delay(self) -> float:
        async with self._lock:
            now = self._clock()
            ready_at = max(now, self._next_slot_at)
            self._next_slot_at = ready_at + self._interval_seconds
            return max(0.0, ready_at - now)

    async def defer_for(self, delay_seconds: float) -> None:
        delay = max(0.0, float(delay_seconds))
        if delay <= 0:
            return

        async with self._lock:
            now = self._clock()
            self._next_slot_at = max(self._next_slot_at, now + delay)


class ChannelTalkCoreRateLimiterRegistry:
    def __init__(
        self,
        *,
        requests_per_second: float | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._requests_per_second = requests_per_second
        self._clock = clock
        self._limiters: dict[
            tuple[str, ChannelTalkCoreRateLimitBucket],
            ChannelTalkCoreBucketRateLimiter,
        ] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        *,
        channel_id: str,
        bucket: ChannelTalkCoreRateLimitBucket,
    ) -> ChannelTalkCoreBucketRateLimiter:
        normalized_channel_id = channel_id.strip()
        if not normalized_channel_id:
            raise ValueError("channel_id is empty")

        key = (normalized_channel_id, bucket)
        async with self._lock:
            limiter = self._limiters.get(key)
            if limiter is None:
                limiter = ChannelTalkCoreBucketRateLimiter(
                    requests_per_second=self._resolve_requests_per_second(),
                    clock=self._clock,
                )
                self._limiters[key] = limiter
            return limiter

    async def get_for_request(
        self,
        *,
        channel_id: str,
        method: str,
        path: str,
    ) -> ChannelTalkCoreBucketRateLimiter:
        bucket = resolve_channel_talk_core_rate_limit_bucket(
            method=method,
            path=path,
        )
        return await self.get(channel_id=channel_id, bucket=bucket)

    def _resolve_requests_per_second(self) -> float:
        if self._requests_per_second is not None:
            return self._requests_per_second
        return settings.CHANNEL_TALK_CORE_API_RPS_LIMIT


def resolve_channel_talk_core_rate_limit_bucket(
    *,
    method: str,
    path: str,
) -> ChannelTalkCoreRateLimitBucket:
    if str(method or "").strip().upper() != "GET":
        return ChannelTalkCoreRateLimitBucket.CORE_DEFAULT

    normalized_path = _normalize_path(path)
    if normalized_path in {"/open/v4/user-chats", "/open/v5/user-chats"}:
        return ChannelTalkCoreRateLimitBucket.USER_CHAT_LIST

    return ChannelTalkCoreRateLimitBucket.CORE_DEFAULT


_registry = ChannelTalkCoreRateLimiterRegistry()


async def get_channel_talk_core_rate_limiter(
    *,
    channel_id: str,
    method: str,
    path: str,
) -> ChannelTalkCoreBucketRateLimiter:
    return await _registry.get_for_request(
        channel_id=channel_id,
        method=method,
        path=path,
    )


def _normalize_path(path: str) -> str:
    text = str(path or "").strip()
    parsed = urlsplit(text)
    normalized = parsed.path if parsed.path else text.split("?", 1)[0]
    normalized = "/" + normalized.strip("/")
    return normalized.rstrip("/") or "/"
