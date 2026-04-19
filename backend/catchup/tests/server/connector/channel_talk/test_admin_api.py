from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsStatus
from catchup.connectors.channel_talk.schemas import ChannelTalkUninstallResult
from catchup.server.connector.channel_talk.admin_api import router
from catchup.server.connector.channel_talk.dependencies import get_channel_talk_service
from catchup.server.error_handlers.channel_talk import (
    register_channel_talk_exception_handlers,
)


class StubChannelTalkService:
    def __init__(self) -> None:
        self.connect_result = ChannelTalkCredentialsStatus(installed=False)
        self.status_result = ChannelTalkCredentialsStatus(installed=False)
        self.uninstall_result = ChannelTalkUninstallResult(removed=False)
        self.last_connect_request = None
        self.connect_error = None

    async def connect(self, request):
        self.last_connect_request = request
        if self.connect_error is not None:
            raise self.connect_error
        return self.connect_result

    async def get_status(self):
        return self.status_result

    async def uninstall(self):
        return self.uninstall_result


class ChannelTalkAdminApiTests(TestCase):
    def setUp(self) -> None:
        self.service = StubChannelTalkService()
        self.app = FastAPI()
        self.app.include_router(router)
        register_channel_talk_exception_handlers(self.app)
        self.app.dependency_overrides[require_admin_user] = lambda: object()
        self.app.dependency_overrides[get_channel_talk_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_post_credentials_returns_connected_payload(self) -> None:
        verified_at = datetime(2026, 4, 19, 8, 30, tzinfo=timezone.utc)
        self.service.connect_result = ChannelTalkCredentialsStatus(
            installed=True,
            channel_id="channel-123",
            channel_name="Support",
            credential_last_verified_at=verified_at,
            webhook_token_configured=True,
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/credentials",
            json={
                "access_key": "access-key",
                "access_secret": "access-secret",
                "webhook_token": "webhook-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "installed": True,
                "channel_id": "channel-123",
                "channel_name": "Support",
                "credential_last_verified_at": verified_at.isoformat(),
                "webhook_token_configured": True,
                "status_reason": None,
                "status": "connected",
                "message": "Channel Talk credentials saved.",
            },
        )
        self.assertEqual(self.service.last_connect_request.access_key, "access-key")
        self.assertEqual(self.service.last_connect_request.access_secret, "access-secret")
        self.assertEqual(self.service.last_connect_request.webhook_token, "webhook-token")

    def test_get_credentials_returns_disconnected_payload(self) -> None:
        self.service.status_result = ChannelTalkCredentialsStatus.disconnected()

        response = self.client.get("/api/v1/admin/connector/channel-talk/credentials")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "installed": False,
                "channel_id": None,
                "channel_name": None,
                "credential_last_verified_at": None,
                "webhook_token_configured": False,
                "status_reason": None,
            },
        )

    def test_delete_credentials_returns_removed_and_not_found_payloads(self) -> None:
        self.service.uninstall_result = ChannelTalkUninstallResult(removed=True)

        removed_response = self.client.delete("/api/v1/admin/connector/channel-talk/credentials")
        self.assertEqual(removed_response.status_code, 200)
        self.assertEqual(
            removed_response.json(),
            {
                "status": "success",
                "message": "Channel Talk credentials removed.",
                "installed": False,
            },
        )

        self.service.uninstall_result = ChannelTalkUninstallResult(removed=False)
        missing_response = self.client.delete("/api/v1/admin/connector/channel-talk/credentials")
        self.assertEqual(missing_response.status_code, 200)
        self.assertEqual(
            missing_response.json(),
            {
                "status": "not_found",
                "message": "Channel Talk credentials were not installed.",
                "installed": False,
            },
        )

    def test_post_credentials_returns_route_scoped_validation_shape(self) -> None:
        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/credentials",
            json={
                "access_key": "access-key",
                "access_secret": "access-secret",
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "invalid_request")
        self.assertEqual(body["detail"]["message"], "Invalid Channel Talk connect request.")
        self.assertTrue(body["detail"]["metadata"]["errors"])

    def test_post_credentials_returns_channel_talk_error_shape(self) -> None:
        self.service.connect_error = ChannelTalkAuthenticationError(
            "Channel Talk credentials are invalid or unauthorized",
            metadata={"status_code": 401, "request_id": "req-123"},
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/credentials",
            json={
                "access_key": "access-key",
                "access_secret": "access-secret",
                "webhook_token": "webhook-token",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "detail": {
                    "code": "invalid_credentials",
                    "message": "Channel Talk credentials are invalid or unauthorized",
                    "metadata": {"status_code": 401, "request_id": "req-123"},
                }
            },
        )
