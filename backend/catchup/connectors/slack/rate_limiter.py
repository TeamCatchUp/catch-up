from __future__ import annotations

import asyncio
from time import monotonic

from catchup.configs.config import settings


class SlackTeamRateLimiter:
    def __init__(
        self,
        rpm_limit: int,
        window_seconds: int,
    ) -> None:
        limit = max(1, int(rpm_limit))
        window = max(1, int(window_seconds))

        self._interval_seconds = window / limit
        self._next_slot_at = 0.0
        self._lock = asyncio.Lock()

    async def acquire_delay(self) -> float:
        async with self._lock:
            now = monotonic()
            ready_at = max(now, self._next_slot_at)
            self._next_slot_at = ready_at + self._interval_seconds
            return max(0.0, ready_at - now)


class SlackRateLimiterRegistry:
    def __init__(self) -> None:
        self._limiters: dict[str, SlackTeamRateLimiter] = {}
        self._lock = asyncio.Lock()

    async def get(self, team_id: str) -> SlackTeamRateLimiter:
        normalized_team_id = team_id.strip()
        if not normalized_team_id:
            raise ValueError("team_id is empty")

        async with self._lock:
            limiter = self._limiters.get(normalized_team_id)
            if limiter is None:
                limiter = SlackTeamRateLimiter(
                    rpm_limit=settings.SLACK_API_RPM_LIMIT,
                    window_seconds=settings.SLACK_API_RATE_LIMIT_WINDOW_SECONDS,
                )
                self._limiters[normalized_team_id] = limiter
            return limiter


_registry = SlackRateLimiterRegistry()


async def get_slack_rate_limiter(team_id: str) -> SlackTeamRateLimiter:
    return await _registry.get(team_id)
