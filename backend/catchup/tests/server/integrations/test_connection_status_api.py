from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.auth.dependencies import require_admin_user
from catchup.server.integrations.api import router
from catchup.server.integrations.connection_status import ConnectionStatus
from catchup.server.integrations.connection_status import ConnectionStatusAdapter
from catchup.server.integrations.connection_status import ConnectionStatusApplication
from catchup.server.integrations.connection_status import ConnectionStatusItem
from catchup.server.integrations.connection_status import ConnectionType


class IntegrationConnectionStatusApiTests(TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[require_admin_user] = lambda: object()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_get_slack_connection_status_uses_canonical_shape(self) -> None:
        connected_at = datetime(2026, 5, 4, 1, 2, 3, tzinfo=timezone.utc)

        with patch(
            "catchup.server.integrations.api.connection_status_application.get_status",
            return_value=ConnectionStatus(
                vendor="slack",
                connected=True,
                connection_type=ConnectionType.OAUTH_TOKEN,
                count=1,
                items=[
                    ConnectionStatusItem(
                        id="T123",
                        name="CatchUp",
                        connected_at=connected_at,
                        metadata={
                            "bot_user_id": "U123",
                            "scopes": ["channels:read"],
                        },
                    )
                ],
            ),
        ):
            response = self.client.get(
                "/api/v1/integrations/slack/connection-status"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "vendor": "slack",
                "connected": True,
                "connection_type": "oauth_token",
                "count": 1,
                "items": [
                    {
                        "id": "T123",
                        "name": "CatchUp",
                        "connected_at": "2026-05-04T01:02:03Z",
                        "metadata": {
                            "bot_user_id": "U123",
                            "scopes": ["channels:read"],
                        },
                    }
                ],
            },
        )

    def test_channel_talk_uses_canonical_underscore_vendor(self) -> None:
        class EmptyProvider:
            def list_github_installation_items(self):
                return []

            def list_slack_oauth_token_items(self):
                return []

            def list_atlassian_oauth_token_items(self):
                return []

            def list_channel_talk_credential_items(self):
                return []

        response = ConnectionStatusApplication(
            provider=EmptyProvider(),
        ).get_status(vendor="channel_talk")

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.vendor, "channel_talk")
        self.assertEqual(response.connection_type, "credential")
        self.assertFalse(response.connected)

    def test_channel_talk_rejects_hyphen_alias(self) -> None:
        class RaisingProvider:
            def list_github_installation_items(self):
                raise AssertionError("provider should not be touched")

            def list_slack_oauth_token_items(self):
                raise AssertionError("provider should not be touched")

            def list_atlassian_oauth_token_items(self):
                raise AssertionError("provider should not be touched")

            def list_channel_talk_credential_items(self):
                raise AssertionError("provider should not be touched")

        response = ConnectionStatusApplication(
            provider=RaisingProvider(),
        ).get_status(vendor=f"channel{'-'}talk")

        self.assertIsNone(response)

    def test_unsupported_vendor_returns_400(self) -> None:
        response = self.client.get(
            "/api/v1/integrations/notion/connection-status"
        )

        self.assertEqual(response.status_code, 400)

    def test_unsupported_vendor_does_not_touch_provider(self) -> None:
        class RaisingProvider:
            def list_github_installation_items(self):
                raise AssertionError("provider should not be touched")

            def list_slack_oauth_token_items(self):
                raise AssertionError("provider should not be touched")

            def list_atlassian_oauth_token_items(self):
                raise AssertionError("provider should not be touched")

            def list_channel_talk_credential_items(self):
                raise AssertionError("provider should not be touched")

        response = ConnectionStatusApplication(
            provider=RaisingProvider(),
        ).get_status(vendor="notion")

        self.assertIsNone(response)


class IntegrationConnectionStatusQueryTests(TestCase):
    def test_slack_status_item_does_not_expose_tokens(self) -> None:
        db = SimpleNamespace(
            rows=[
                SimpleNamespace(
                    team_id="T123",
                    team_name="CatchUp",
                    bot_user_id="U123",
                    bot_scopes="channels:read users:read",
                    bot_access_token="xoxb-secret",
                    created_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
                )
            ],
        )

        with patch(
            "catchup.server.integrations.connection_status.slack_oauth_repository.get_all_slack_tokens",
            return_value=db.rows,
        ):
            items = ConnectionStatusAdapter(
                db=db,
            ).list_slack_oauth_token_items()

        self.assertEqual(len(items), 1)
        payload = items[0].model_dump(mode="json")
        self.assertEqual(payload["id"], "T123")
        self.assertNotIn("bot_access_token", payload["metadata"])
        self.assertNotIn("xoxb-secret", str(payload))

    def test_channel_talk_status_uses_record_fields_only(self) -> None:
        verified_at = datetime(2026, 5, 4, tzinfo=timezone.utc)
        channel_record = SimpleNamespace(
            channel_id="channel-123",
            channel_name="Support",
            webhook_token="webhook-secret",
            credential_last_verified_at=verified_at,
        )

        with (
            patch(
                "catchup.server.integrations.connection_status.ChannelTalkCredentialsRepository.list_connections",
                return_value=[channel_record],
            ),
            patch(
                "catchup.server.integrations.connection_status.ChannelTalkDocumentCredentialsRepository.list_document_connections",
                return_value=[],
            ),
        ):
            items = ConnectionStatusAdapter(
                db=SimpleNamespace(),
            ).list_channel_talk_credential_items()

        self.assertEqual(len(items), 1)
        payload = items[0].model_dump(mode="json")
        self.assertEqual(payload["id"], "channel-123")
        self.assertEqual(
            payload["metadata"],
            {
                "credential_type": "channel",
                "last_verified_at": "2026-05-04T00:00:00Z",
                "webhook_token_configured": True,
            },
        )
        self.assertNotIn("manager_id", payload["metadata"])
        self.assertNotIn("manager_name", payload["metadata"])
        self.assertNotIn("webhook-secret", str(payload))
