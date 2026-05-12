from __future__ import annotations

from unittest import IsolatedAsyncioTestCase

from catchup.connectors.channel_talk.document_space.rate_limiter import (
    ChannelTalkDocumentSpaceRateLimiter,
)
from catchup.connectors.channel_talk.document_space.rate_limiter import (
    ChannelTalkDocumentSpaceRateLimiterRegistry,
)


class ManualClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ChannelTalkDocumentSpaceRateLimiterTests(IsolatedAsyncioTestCase):
    async def test_document_space_limiter_spaces_requests_without_burst(self) -> None:
        clock = ManualClock()
        limiter = ChannelTalkDocumentSpaceRateLimiter(
            requests_per_second=2.0,
            clock=clock,
        )

        self.assertEqual(await limiter.acquire_delay(), 0.0)
        self.assertEqual(await limiter.acquire_delay(), 0.5)

        clock.advance(0.25)

        self.assertEqual(await limiter.acquire_delay(), 0.75)

    async def test_document_space_limiter_caps_configured_rps_at_documented_limit(
        self,
    ) -> None:
        limiter = ChannelTalkDocumentSpaceRateLimiter(
            requests_per_second=20.0,
            clock=ManualClock(),
        )

        self.assertEqual(await limiter.acquire_delay(), 0.0)
        self.assertAlmostEqual(await limiter.acquire_delay(), 0.1)

    async def test_document_space_limiter_defer_for_pushes_next_slot_to_retry_window(
        self,
    ) -> None:
        clock = ManualClock()
        limiter = ChannelTalkDocumentSpaceRateLimiter(
            requests_per_second=2.0,
            clock=clock,
        )

        self.assertEqual(await limiter.acquire_delay(), 0.0)

        await limiter.defer_for(3.0)

        self.assertEqual(await limiter.acquire_delay(), 3.0)

        clock.advance(1.0)

        self.assertEqual(await limiter.acquire_delay(), 2.5)

    def test_document_space_limiter_rejects_non_positive_rps(self) -> None:
        for requests_per_second in (0.0, -1.0):
            with self.assertRaisesRegex(
                ValueError,
                "requests_per_second must be positive",
            ):
                ChannelTalkDocumentSpaceRateLimiter(
                    requests_per_second=requests_per_second,
                )

    async def test_registry_keeps_space_limiters_independent(self) -> None:
        clock = ManualClock()
        registry = ChannelTalkDocumentSpaceRateLimiterRegistry(
            requests_per_second=2.0,
            clock=clock,
        )

        first_space_limiter = await registry.get(space_id="space-1")
        same_space_limiter = await registry.get(space_id="space-1")
        other_space_limiter = await registry.get(space_id="space-2")

        self.assertIs(first_space_limiter, same_space_limiter)
        self.assertIsNot(first_space_limiter, other_space_limiter)

        self.assertEqual(await first_space_limiter.acquire_delay(), 0.0)
        self.assertEqual(await first_space_limiter.acquire_delay(), 0.5)
        self.assertEqual(await other_space_limiter.acquire_delay(), 0.0)

    async def test_registry_rejects_empty_space_id(self) -> None:
        registry = ChannelTalkDocumentSpaceRateLimiterRegistry(
            requests_per_second=2.0,
        )

        with self.assertRaisesRegex(ValueError, "space_id is empty"):
            await registry.get(space_id=" ")
