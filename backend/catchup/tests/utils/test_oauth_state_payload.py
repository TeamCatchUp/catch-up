from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.utils import redis as redis_utils
from catchup.workflow_credentials.oauth import consume_workflow_redirect_after


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def getdel(self, key: str):
        return self.values.pop(key, None)


class OAuthStatePayloadTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.redis = _FakeRedis()
        self.patcher = patch(
            "catchup.utils.redis.get_redis_client",
            return_value=self.redis,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    async def test_payload_round_trips_once(self) -> None:
        payload = {
            "purpose": "workflow_personal",
            "vendor": "slack",
            "user_id": 1,
            "workspace_id": 2,
            "redirect_after": "/settings/credentials",
        }

        await redis_utils.store_oauth_state_payload(
            provider="slack",
            state="state-1",
            payload=payload,
        )

        self.assertEqual(
            await redis_utils.consume_oauth_state_payload(
                provider="slack",
                state="state-1",
            ),
            payload,
        )
        self.assertIsNone(
            await redis_utils.consume_oauth_state_payload(
                provider="slack",
                state="state-1",
            )
        )

    async def test_legacy_one_value_consumes_as_sync_install(self) -> None:
        self.redis.values["oauth:state:atlassian:legacy"] = "1"

        payload = await redis_utils.consume_oauth_state_payload(
            provider="atlassian",
            state="legacy",
        )

        self.assertEqual(payload["purpose"], "sync_install")
        self.assertEqual(payload["vendor"], "atlassian")
        self.assertTrue(payload["legacy"])

    async def test_malformed_payload_is_rejected_after_delete(self) -> None:
        self.redis.values["oauth:state:github:bad"] = "not-json"

        self.assertIsNone(
            await redis_utils.consume_oauth_state_payload(
                provider="github",
                state="bad",
            )
        )
        self.assertEqual(self.redis.values, {})

    async def test_consume_workflow_redirect_after_rejects_sync_state(self) -> None:
        await redis_utils.store_oauth_state_payload(
            provider="slack",
            state="sync",
            payload={"purpose": "sync_install", "vendor": "slack"},
        )

        self.assertIsNone(
            await consume_workflow_redirect_after(
                provider="slack",
                state="sync",
            )
        )

    async def test_consume_workflow_redirect_after_returns_workflow_redirect(self) -> None:
        await redis_utils.store_oauth_state_payload(
            provider="github",
            state="workflow",
            payload={
                "purpose": "workflow_personal",
                "vendor": "github",
                "redirect_after": "/settings/credentials",
            },
        )

        self.assertEqual(
            await consume_workflow_redirect_after(
                provider="github",
                state="workflow",
            ),
            "/settings/credentials",
        )
