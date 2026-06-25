from __future__ import annotations

from typing import Any
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.agents.triggers.resolver import AgentTriggerIngressResult
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.server.connector.channel_talk.webhook_api import router
from catchup.sync.incremental.schemas import IncrementalIngestResult

_WEBHOOK_MODULE = "catchup.server.connector.channel_talk.webhook_api"
_LOAD_CONNECTION = f"{_WEBHOOK_MODULE}.load_channel_talk_connection"
_RUN_IN_THREADPOOL = f"{_WEBHOOK_MODULE}.run_in_threadpool"
_GET_INCREMENTAL_SERVICE = f"{_WEBHOOK_MODULE}.get_incremental_service"
_HANDLE_AGENT_TRIGGER = f"{_WEBHOOK_MODULE}.handle_verified_webhook_event"
_RESOLVE_CHANNEL_TALK = f"{_WEBHOOK_MODULE}.resolve_channel_talk_user_chat_event"


async def _run_immediately(func, *args, **kwargs) -> Any:
    return func(*args, **kwargs)


def _message_payload(chat_type: str) -> dict[str, object]:
    return {
        "type": "message",
        "entity": {
            "channelId": "channel-123",
            "chatType": chat_type,
            "chatId": "chat-123",
            "id": "message-123",
        },
    }


class StubIncrementalService:
    def __init__(self) -> None:
        self.changes: list[Any] = []

    async def dispatch_changes(self, *, changes: list[Any]) -> IncrementalIngestResult:
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
        self.agent_dispatch_patcher = patch(
            _HANDLE_AGENT_TRIGGER,
            return_value=AgentTriggerIngressResult(
                status="ignored",
                reason="no_matching_trigger",
            ),
        )
        self.agent_dispatch = self.agent_dispatch_patcher.start()
        self.addCleanup(self.agent_dispatch_patcher.stop)

    def test_webhook_accepts_matching_token(self) -> None:
        with patch(_LOAD_CONNECTION, return_value=self.connection) as load_connection:
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json={
                    "event": "push",
                    "type": "message",
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
        self.agent_dispatch.assert_called_once()
        self.assertEqual(len(self.service.changes), 1)
        change = self.service.changes[0]
        self.assertEqual(change.scope_id, "channel-123")
        self.assertEqual(change.record_type, "user_chat")
        self.assertEqual(change.record_id, "chat-123")

    def test_webhook_rejects_missing_token(self) -> None:
        response = self.client.post(
            "/api/v1/channel_talk/webhooks",
            json={
                "type": "message",
                "entity": {
                    "channelId": "channel-123",
                    "chatType": "userChat",
                    "chatId": "chat-123",
                },
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.changes, [])

    def test_webhook_rejects_wrong_token(self) -> None:
        with patch(_LOAD_CONNECTION, return_value=self.connection):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=wrong-token",
                json={
                    "type": "message",
                    "entity": {
                        "channelId": "channel-123",
                        "chatType": "userChat",
                        "chatId": "chat-123",
                    },
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.changes, [])

    def test_webhook_rejects_unconfigured_token(self) -> None:
        connection = ChannelTalkCredentialsRecord(
            channel_id="channel-123",
            channel_name="Support",
            webhook_token=None,
        )
        with patch(_LOAD_CONNECTION, return_value=connection):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json={
                    "type": "message",
                    "entity": {
                        "channelId": "channel-123",
                        "chatType": "userChat",
                        "chatId": "chat-123",
                    },
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.changes, [])

    def test_webhook_rejects_unknown_channel_as_auth_failure(self) -> None:
        with patch(_LOAD_CONNECTION, return_value=None):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json={
                    "type": "message",
                    "entity": {
                        "channelId": "unknown-channel",
                        "chatType": "userChat",
                        "chatId": "chat-123",
                    },
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.changes, [])

    def test_webhook_accepts_agent_trigger_only_when_sync_ignores_event(self) -> None:
        self.agent_dispatch.return_value = AgentTriggerIngressResult(
            status="accepted",
            run_ids=[44],
            matched_count=1,
        )
        with patch(_LOAD_CONNECTION, return_value=self.connection):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json=_message_payload("groupChat"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")
        self.assertEqual(response.json()["agent_run_ids"], [44])

    def test_webhook_agent_trigger_failure_with_sync_changes_is_retryable(self) -> None:
        self.agent_dispatch.side_effect = RuntimeError("agent trigger failed")
        with patch(_LOAD_CONNECTION, return_value=self.connection):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json=_message_payload("userChat"),
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Agent trigger dispatch failed")
        self.assertEqual(self.service.changes, [])

    def test_webhook_sync_resolve_failure_does_not_skip_agent_trigger(self) -> None:
        with (
            patch(_LOAD_CONNECTION, return_value=self.connection),
            patch(
                _RESOLVE_CHANNEL_TALK,
                side_effect=RuntimeError("sync resolve failed"),
            ),
        ):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json=_message_payload("userChat"),
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Incremental sync resolve failed")
        self.agent_dispatch.assert_called_once()

    def test_webhook_agent_trigger_only_failure_is_retryable(self) -> None:
        self.agent_dispatch.side_effect = RuntimeError("agent trigger failed")
        with patch(_LOAD_CONNECTION, return_value=self.connection):
            response = self.client.post(
                "/api/v1/channel_talk/webhooks?token=webhook-token",
                json=_message_payload("groupChat"),
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Agent trigger dispatch failed")
