from __future__ import annotations

from unittest import IsolatedAsyncioTestCase

from catchup.connectors.channel_talk.core.rate_limiter import (
    ChannelTalkCoreBucketRateLimiter,
)
from catchup.connectors.channel_talk.core.rate_limiter import (
    ChannelTalkCoreRateLimitBucket,
)
from catchup.connectors.channel_talk.core.rate_limiter import (
    ChannelTalkCoreRateLimiterRegistry,
)
from catchup.connectors.channel_talk.core.rate_limiter import (
    resolve_channel_talk_core_rate_limit_bucket,
)


class ManualClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ChannelTalkCoreRateLimiterTests(IsolatedAsyncioTestCase):
    def test_resolves_user_chat_list_bucket_only_for_collection_endpoint(self) -> None:
        self.assertEqual(
            resolve_channel_talk_core_rate_limit_bucket(
                method="GET",
                path="/open/v5/user-chats",
            ),
            ChannelTalkCoreRateLimitBucket.USER_CHAT_LIST,
        )
        self.assertEqual(
            resolve_channel_talk_core_rate_limit_bucket(
                method="GET",
                path="https://api.channel.io/open/v4/user-chats?state=opened",
            ),
            ChannelTalkCoreRateLimitBucket.USER_CHAT_LIST,
        )

        for path in (
            "/open/v5/user-chats/chat-1",
            "/open/v5/user-chats/chat-1/messages",
            "/open/v5/managers",
        ):
            self.assertEqual(
                resolve_channel_talk_core_rate_limit_bucket(
                    method="GET",
                    path=path,
                ),
                ChannelTalkCoreRateLimitBucket.CORE_DEFAULT,
            )

    def test_non_get_user_chat_collection_request_uses_default_bucket(self) -> None:
        self.assertEqual(
            resolve_channel_talk_core_rate_limit_bucket(
                method="POST",
                path="/open/v5/user-chats",
            ),
            ChannelTalkCoreRateLimitBucket.CORE_DEFAULT,
        )

    async def test_bucket_limiter_spaces_requests_without_burst(self) -> None:
        clock = ManualClock()
        limiter = ChannelTalkCoreBucketRateLimiter(
            requests_per_second=2.0,
            clock=clock,
        )

        self.assertEqual(await limiter.acquire_delay(), 0.0)
        self.assertEqual(await limiter.acquire_delay(), 0.5)

        clock.advance(0.25)

        self.assertEqual(await limiter.acquire_delay(), 0.75)

    async def test_bucket_limiter_caps_configured_rps_at_documented_refill_rate(self) -> None:
        limiter = ChannelTalkCoreBucketRateLimiter(
            requests_per_second=20.0,
            clock=ManualClock(),
        )

        self.assertEqual(await limiter.acquire_delay(), 0.0)
        self.assertAlmostEqual(await limiter.acquire_delay(), 0.1)

    def test_bucket_limiter_rejects_non_positive_rps(self) -> None:
        for requests_per_second in (0.0, -1.0):
            with self.assertRaisesRegex(
                ValueError,
                "requests_per_second must be positive",
            ):
                ChannelTalkCoreBucketRateLimiter(
                    requests_per_second=requests_per_second,
                )

    async def test_registry_keeps_channel_and_bucket_limiters_independent(self) -> None:
        clock = ManualClock()
        registry = ChannelTalkCoreRateLimiterRegistry(
            requests_per_second=2.0,
            clock=clock,
        )

        user_chat_limiter = await registry.get_for_request(
            channel_id="channel-1",
            method="GET",
            path="/open/v5/user-chats",
        )
        same_user_chat_limiter = await registry.get_for_request(
            channel_id="channel-1",
            method="GET",
            path="/open/v5/user-chats?state=opened",
        )
        default_limiter = await registry.get_for_request(
            channel_id="channel-1",
            method="GET",
            path="/open/v5/user-chats/chat-1/messages",
        )
        other_channel_limiter = await registry.get_for_request(
            channel_id="channel-2",
            method="GET",
            path="/open/v5/user-chats",
        )

        self.assertIs(user_chat_limiter, same_user_chat_limiter)
        self.assertIsNot(user_chat_limiter, default_limiter)
        self.assertIsNot(user_chat_limiter, other_channel_limiter)

        self.assertEqual(await user_chat_limiter.acquire_delay(), 0.0)
        self.assertEqual(await user_chat_limiter.acquire_delay(), 0.5)
        self.assertEqual(await default_limiter.acquire_delay(), 0.0)
        self.assertEqual(await other_channel_limiter.acquire_delay(), 0.0)

    async def test_registry_rejects_empty_channel_id(self) -> None:
        registry = ChannelTalkCoreRateLimiterRegistry(requests_per_second=2.0)

        with self.assertRaisesRegex(ValueError, "channel_id is empty"):
            await registry.get(
                channel_id=" ",
                bucket=ChannelTalkCoreRateLimitBucket.USER_CHAT_LIST,
            )
