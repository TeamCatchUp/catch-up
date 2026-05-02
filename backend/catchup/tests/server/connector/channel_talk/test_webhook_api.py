from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.server.connector.channel_talk.webhook_api import router
from catchup.sync.incremental.schemas import IncrementalIngestResult

_WEBHOOK_MODULE = "catchup.server.connector.channel_talk.webhook_api"
_LOAD_CONNECTION = f"{_WEBHOOK_MODULE}.load_channel_talk_connection"
_RUN_IN_THREADPOOL = f"{_WEBHOOK_MODULE}.run_in_threadpool"
_GET_INCREMENTAL_SERVICE = f"{_WEBHOOK_MODULE}.get_incremental_service"


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class StubIncrementalService:
    def __init__(self) -> None:
        self.changes = []

    async def dispatch_changes(self, *, changes):
        self.changes = list(changes)
        return IncrementalIngestResult(
            record_keys=[change.record_key for change in self.changes],
            blocked_count=0,
            blocked_target_keys=[],
        )


class ChannelTalkWebhookApiTests(TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.service = StubIncrementalService()
        self.connection = ChannelTalkCredentialsRecord(
            channel_id="channel-123",
            channel_name="Support",
            webhook_token="webhook-token",
        )
        self.run_in_threadpool_patcher = patch(
            _RUN_IN_THREADPOOL,
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)
        self.service_patcher = patch(
            _GET_INCREMENTAL_SERVICE,
            return_value=self.service,
        )
        self.service_patcher.start()
        self.addCleanup(self.service_patcher.stop)

    def test_webhook_accepts_configured_channel_talk_url(self) -> None:
        with patch(_LOAD_CONNECTION, return_value=self.connection) as load_connection:
            response = self.client.post(
                "/api/v1/channel_talk/webhooks",
                json={
                    "event": "push",
                    "type": "Message",
                    "entity": {
                        "channelId": "channel-123",
                        "chatType": "userChat",
                        "chatId": "chat-123",
                        "updatedAt": 1776825600000,
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")
        load_connection.assert_called_once_with("channel-123")
        self.assertEqual(len(self.service.changes), 1)
        change = self.service.changes[0]
        self.assertEqual(change.scope_id, "channel-123")
        self.assertEqual(change.record_type, "user_chat")
        self.assertEqual(change.record_id, "chat-123")

    def test_webhook_rejects_wrong_optional_token(self) -> None:
        with patch(_LOAD_CONNECTION, return_value=self.connection):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=wrong-token",
                json={
                    "type": "Message",
                    "entity": {
                        "channelId": "channel-123",
                        "chatType": "userChat",
                        "chatId": "chat-123",
                    },
                },
            )

        self.assertEqual(response.status_code, 401)
