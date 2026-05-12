from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import monotonic

from catchup.configs.config import settings

CHANNEL_TALK_DOCUMENTS_API_DOCUMENTED_RPS = 10.0


class ChannelTalkDocumentSpaceRateLimiter:
    # 1단계: Documents API 문서의 space당 초당 요청 제한을 단일 버킷으로 모델링한다.
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
            CHANNEL_TALK_DOCUMENTS_API_DOCUMENTED_RPS,
        )
        self._next_slot_at = 0.0
        self._clock = clock
        self._lock = asyncio.Lock()

    async def acquire_delay(self) -> float:
        # 2단계: 단일 프로세스 안에서 같은 space의 요청을 직렬화해 burst 없이 흘린다.
        async with self._lock:
            now = self._clock()
            ready_at = max(now, self._next_slot_at)
            self._next_slot_at = ready_at + self._interval_seconds
            return max(0.0, ready_at - now)


class ChannelTalkDocumentSpaceRateLimiterRegistry:
    # 3단계: space_id별 limiter를 따로 보관해 각 Document Space의 quota를 독립적으로 보호한다.
    def __init__(
        self,
        *,
        requests_per_second: float | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._requests_per_second = requests_per_second
        self._clock = clock
        self._limiters: dict[str, ChannelTalkDocumentSpaceRateLimiter] = {}
        self._lock = asyncio.Lock()

    async def get(
        self,
        *,
        space_id: str,
    ) -> ChannelTalkDocumentSpaceRateLimiter:
        normalized_space_id = space_id.strip()
        if not normalized_space_id:
            raise ValueError("space_id is empty")

        async with self._lock:
            limiter = self._limiters.get(normalized_space_id)
            if limiter is None:
                limiter = ChannelTalkDocumentSpaceRateLimiter(
                    requests_per_second=self._resolve_requests_per_second(),
                    clock=self._clock,
                )
                self._limiters[normalized_space_id] = limiter
            return limiter

    def _resolve_requests_per_second(self) -> float:
        if self._requests_per_second is not None:
            return self._requests_per_second
        return settings.CHANNEL_TALK_DOCUMENTS_API_RPS_LIMIT


_registry = ChannelTalkDocumentSpaceRateLimiterRegistry()


async def get_channel_talk_document_space_rate_limiter(
    *,
    space_id: str,
) -> ChannelTalkDocumentSpaceRateLimiter:
    # 4단계: 호출자는 space_id만 넘겨 해당 Document Space의 limiter를 재사용한다.
    return await _registry.get(space_id=space_id)
