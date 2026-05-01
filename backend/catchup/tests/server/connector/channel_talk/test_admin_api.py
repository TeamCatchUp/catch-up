from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkManager
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentUninstallResult,
)
from catchup.server.connector.channel_talk.admin_api import router
from catchup.server.connector.channel_talk.dependencies import (
    get_channel_talk_document_metadata_task_runner,
)
from catchup.server.connector.channel_talk.dependencies import (
    get_channel_talk_document_service,
)
from catchup.server.connector.channel_talk.dependencies import (
    get_channel_talk_metadata_task_runner,
)
from catchup.server.connector.channel_talk.dependencies import get_channel_talk_service
from catchup.server.error_handlers.channel_talk import (
    register_channel_talk_exception_handlers,
)


class StubChannelTalkService:
    def __init__(self) -> None:
        self.connect_result = ChannelTalkCredentialsStatus(installed=False)
        self.validate_result = ChannelTalkCurrentChannel(
            channel=ChannelTalkChannel(id="channel-123", name="Support"),
            manager=ChannelTalkManager(id="manager-7", name="Jane"),
        )
        self.status_result = ChannelTalkCredentialsStatus(installed=False)
        self.list_statuses_result: list[ChannelTalkCredentialsStatus] = []
        self.uninstall_result = ChannelTalkUninstallResult(removed=False)
        self.last_connect_request = None
        self.last_validate_request = None
        self.last_uninstall_channel_id = None
        self.connect_error = None
        self.validate_error = None

    async def connect(self, request):
        self.last_connect_request = request
        if self.connect_error is not None:
            raise self.connect_error
        return self.connect_result

    async def validate_credentials(self, request):
        self.last_validate_request = request
        if self.validate_error is not None:
            raise self.validate_error
        return self.validate_result

    async def get_status(self):
        return self.status_result

    async def list_statuses(self):
        return self.list_statuses_result

    async def uninstall(self, channel_id):
        self.last_uninstall_channel_id = channel_id
        return self.uninstall_result


class StubChannelTalkDocumentService:
    def __init__(self) -> None:
        self.connect_result = ChannelTalkDocumentCredentialsStatus(installed=False)
        self.validate_result = ChannelTalkDocumentCredentialsStatus(
            installed=False,
            channel_id="channel-123",
            space_id="space-123",
            space_name="Help Center",
            association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
        )
        self.status_result = ChannelTalkDocumentCredentialsStatus(installed=False)
        self.list_statuses_result: list[ChannelTalkDocumentCredentialsStatus] = []
        self.uninstall_result = ChannelTalkDocumentUninstallResult(removed=False)
        self.last_connect_request = None
        self.last_validate_request = None
        self.last_uninstall_space_id = None
        self.connect_error = None
        self.validate_error = None

    async def connect(self, request):
        self.last_connect_request = request
        if self.connect_error is not None:
            raise self.connect_error
        return self.connect_result

    async def validate_connection(self, request):
        self.last_validate_request = request
        if self.validate_error is not None:
            raise self.validate_error
        return self.validate_result

    async def get_status(self):
        return self.status_result

    async def list_statuses(self):
        return self.list_statuses_result

    async def uninstall(self, space_id):
        self.last_uninstall_space_id = space_id
        return self.uninstall_result


class ChannelTalkAdminApiTests(TestCase):
    def setUp(self) -> None:
        self.service = StubChannelTalkService()
        self.document_service = StubChannelTalkDocumentService()
        self.background_sync_calls: list[str] = []
        self.document_background_sync_calls: list[str] = []

        async def background_runner(channel_id: str) -> None:
            self.background_sync_calls.append(channel_id)

        async def document_background_runner(channel_id: str) -> None:
            self.document_background_sync_calls.append(channel_id)

        self.app = FastAPI()
        self.app.include_router(router)
        register_channel_talk_exception_handlers(self.app)
        self.app.dependency_overrides[require_admin_user] = lambda: object()
        self.app.dependency_overrides[get_channel_talk_service] = lambda: self.service
        self.app.dependency_overrides[get_channel_talk_document_service] = lambda: self.document_service
        self.app.dependency_overrides[get_channel_talk_metadata_task_runner] = lambda: background_runner
        self.app.dependency_overrides[get_channel_talk_document_metadata_task_runner] = (
            lambda: document_background_runner
        )
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_validate_credentials_returns_channel_payload_without_saving(self) -> None:
        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/credentials/validate",
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
                "status": "validated",
                "channel_id": "channel-123",
                "channel_name": "Support",
                "manager_id": "manager-7",
                "manager_name": "Jane",
                "webhook_token_configured": True,
            },
        )
        self.assertEqual(self.service.last_validate_request.access_key, "access-key")
        self.assertIsNone(self.service.last_connect_request)
        self.assertEqual(self.background_sync_calls, [])

    def test_validate_credentials_returns_channel_talk_error_shape(self) -> None:
        self.service.validate_error = ChannelTalkAuthenticationError(
            "Channel Talk credentials are invalid or unauthorized",
            metadata={"status_code": 401, "request_id": "req-validate"},
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/credentials/validate",
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
                    "metadata": {"status_code": 401, "request_id": "req-validate"},
                }
            },
        )
        self.assertIsNone(self.service.last_connect_request)
        self.assertEqual(self.background_sync_calls, [])

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
        self.assertEqual(self.background_sync_calls, ["channel-123"])

    def test_get_credentials_returns_list_payload(self) -> None:
        verified_at = datetime(2026, 4, 19, 8, 30, tzinfo=timezone.utc)
        self.service.list_statuses_result = [
            ChannelTalkCredentialsStatus(
                installed=True,
                channel_id="channel-123",
                channel_name="Support",
                credential_last_verified_at=verified_at,
                webhook_token_configured=True,
            ),
            ChannelTalkCredentialsStatus(
                installed=True,
                channel_id="channel-456",
                channel_name="Sales",
                credential_last_verified_at=verified_at,
                webhook_token_configured=False,
            ),
        ]

        response = self.client.get("/api/v1/admin/connector/channel-talk/credentials")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "installed": True,
                    "channel_id": "channel-123",
                    "channel_name": "Support",
                    "credential_last_verified_at": verified_at.isoformat(),
                    "webhook_token_configured": True,
                    "status_reason": None,
                },
                {
                    "installed": True,
                    "channel_id": "channel-456",
                    "channel_name": "Sales",
                    "credential_last_verified_at": verified_at.isoformat(),
                    "webhook_token_configured": False,
                    "status_reason": None,
                },
            ],
        )

    def test_get_credentials_returns_empty_list_when_disconnected(self) -> None:
        response = self.client.get("/api/v1/admin/connector/channel-talk/credentials")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_delete_credentials_uses_channel_id_and_returns_removed_and_not_found_payloads(self) -> None:
        self.service.uninstall_result = ChannelTalkUninstallResult(removed=True)

        removed_response = self.client.delete(
            "/api/v1/admin/connector/channel-talk/credentials",
            params={"channel_id": "channel-123"},
        )
        self.assertEqual(removed_response.status_code, 200)
        self.assertEqual(
            removed_response.json(),
            {
                "status": "success",
                "message": "Channel Talk credentials removed.",
                "installed": False,
            },
        )
        self.assertEqual(self.service.last_uninstall_channel_id, "channel-123")

        self.service.uninstall_result = ChannelTalkUninstallResult(removed=False)
        missing_response = self.client.delete(
            "/api/v1/admin/connector/channel-talk/credentials",
            params={"channel_id": "channel-456"},
        )
        self.assertEqual(missing_response.status_code, 200)
        self.assertEqual(
            missing_response.json(),
            {
                "status": "not_found",
                "message": "Channel Talk credentials were not installed.",
                "installed": False,
            },
        )
        self.assertEqual(self.service.last_uninstall_channel_id, "channel-456")

    def test_delete_credentials_requires_channel_id(self) -> None:
        response = self.client.delete("/api/v1/admin/connector/channel-talk/credentials")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertIsNone(self.service.last_uninstall_channel_id)

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
        self.assertEqual(self.background_sync_calls, [])

    def test_validate_document_credentials_returns_space_payload_without_saving(self) -> None:
        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials/validate",
            json={
                "access_key": "documents-key",
                "access_secret": "documents-secret",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "validated",
                "channel_id": "channel-123",
                "space_id": "space-123",
                "space_name": "Help Center",
                "association_status": "api_verified",
            },
        )
        self.assertEqual(
            self.document_service.last_validate_request.access_key,
            "documents-key",
        )
        self.assertIsNone(self.document_service.last_connect_request)
        self.assertEqual(self.document_background_sync_calls, [])

    def test_validate_document_credentials_base_channel_missing_fails(self) -> None:
        self.document_service.validate_error = ChannelTalkValidationError(
            "Channel Talk credentials are not installed"
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials/validate",
            json={
                "access_key": "documents-key",
                "access_secret": "documents-secret",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertIsNone(self.document_service.last_connect_request)
        self.assertEqual(self.document_background_sync_calls, [])

    def test_validate_document_credentials_channel_conflict_fails(self) -> None:
        self.document_service.validate_error = ChannelTalkConflictError(
            "Channel Talk Documents space does not match the installed Channel Talk channel"
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials/validate",
            json={
                "access_key": "documents-key",
                "access_secret": "documents-secret",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "connection_conflict")
        self.assertIsNone(self.document_service.last_connect_request)
        self.assertEqual(self.document_background_sync_calls, [])

    def test_post_document_credentials_returns_connected_payload_and_schedules_background_sync(self) -> None:
        verified_at = datetime(2026, 4, 25, 8, 30, tzinfo=timezone.utc)
        self.document_service.connect_result = ChannelTalkDocumentCredentialsStatus(
            installed=True,
            channel_id="channel-123",
            space_id="space-123",
            space_name="Help Center",
            credential_last_verified_at=verified_at,
            association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials",
            json={
                "access_key": "documents-key",
                "access_secret": "documents-secret",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body,
            {
                "installed": True,
                "channel_id": "channel-123",
                "space_id": "space-123",
                "space_name": "Help Center",
                "credential_last_verified_at": verified_at.isoformat(),
                "association_status": "api_verified",
                "status_reason": None,
                "status": "connected",
                "message": "Channel Talk Documents credentials saved.",
            },
        )
        self.assertNotIn("access_secret", body)
        self.assertEqual(self.document_service.last_connect_request.access_key, "documents-key")
        self.assertEqual(
            self.document_service.last_connect_request.access_secret,
            "documents-secret",
        )
        self.assertEqual(self.document_background_sync_calls, ["channel-123"])

    def test_get_document_credentials_returns_list_payload_without_secret(self) -> None:
        verified_at = datetime(2026, 4, 25, 8, 30, tzinfo=timezone.utc)
        self.document_service.list_statuses_result = [
            ChannelTalkDocumentCredentialsStatus(
                installed=True,
                channel_id="channel-123",
                space_id="space-123",
                space_name="Help Center",
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            ),
            ChannelTalkDocumentCredentialsStatus(
                installed=True,
                channel_id="channel-456",
                space_id="space-456",
                space_name="Sales Docs",
                credential_last_verified_at=verified_at,
                association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            ),
        ]

        response = self.client.get(
            "/api/v1/admin/connector/channel-talk/documents/credentials"
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["space_id"] for item in body], ["space-123", "space-456"])
        self.assertEqual(body[0]["association_status"], "api_verified")
        self.assertNotIn("access_secret", body[0])

    def test_delete_document_credentials_uses_space_id_and_returns_removed_and_not_found_payloads(self) -> None:
        self.document_service.uninstall_result = ChannelTalkDocumentUninstallResult(removed=True)

        removed_response = self.client.delete(
            "/api/v1/admin/connector/channel-talk/documents/credentials",
            params={"space_id": "space-123"},
        )
        self.assertEqual(removed_response.status_code, 200)
        self.assertEqual(
            removed_response.json(),
            {
                "status": "success",
                "message": "Channel Talk Documents credentials removed.",
                "installed": False,
            },
        )
        self.assertEqual(self.document_service.last_uninstall_space_id, "space-123")

        self.document_service.uninstall_result = ChannelTalkDocumentUninstallResult(removed=False)
        missing_response = self.client.delete(
            "/api/v1/admin/connector/channel-talk/documents/credentials",
            params={"space_id": "space-456"},
        )
        self.assertEqual(missing_response.status_code, 200)
        self.assertEqual(
            missing_response.json(),
            {
                "status": "not_found",
                "message": "Channel Talk Documents credentials were not installed.",
                "installed": False,
            },
        )
        self.assertEqual(self.document_service.last_uninstall_space_id, "space-456")

    def test_delete_document_credentials_requires_space_id(self) -> None:
        response = self.client.delete(
            "/api/v1/admin/connector/channel-talk/documents/credentials"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertIsNone(self.document_service.last_uninstall_space_id)

    def test_post_document_credentials_base_channel_missing_fails(self) -> None:
        self.document_service.connect_error = ChannelTalkValidationError(
            "Channel Talk credentials are not installed"
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials",
            json={
                "access_key": "documents-key",
                "access_secret": "documents-secret",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "invalid_request")
        self.assertEqual(self.document_background_sync_calls, [])

    def test_post_document_credentials_channel_conflict_fails(self) -> None:
        self.document_service.connect_error = ChannelTalkConflictError(
            "Channel Talk Documents space does not match the installed Channel Talk channel"
        )

        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials",
            json={
                "access_key": "documents-key",
                "access_secret": "documents-secret",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "connection_conflict")
        self.assertEqual(self.document_background_sync_calls, [])

    def test_post_document_credentials_validation_shape_matches_channel_talk_handler(self) -> None:
        response = self.client.post(
            "/api/v1/admin/connector/channel-talk/documents/credentials",
            json={"access_key": "documents-key"},
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "invalid_request")
        self.assertEqual(body["detail"]["message"], "Invalid Channel Talk connect request.")
        self.assertTrue(body["detail"]["metadata"]["errors"])
