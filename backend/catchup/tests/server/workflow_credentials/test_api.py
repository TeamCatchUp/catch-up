from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.security.credential_crypto import CredentialCryptoError
from catchup.server.workflow_credentials.api import router


class WorkflowCredentialApiTests(TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(router)
        self.user = SimpleNamespace(id=7)
        self.db = Mock()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()

    @contextmanager
    def db_session(self):
        yield self.db

    def test_list_omits_secret_payload(self) -> None:
        now = datetime(2026, 5, 10, tzinfo=timezone.utc)
        credential = SimpleNamespace(
            id=1,
            display_name="Slack",
            vendor="slack",
            auth_type="oauth2_user",
            ownership_type="user_personal",
            workspace_id=2,
            owner_user_id=7,
            external_tenant_id="T123",
            external_tenant_name="Team",
            external_account_id="U123",
            external_account_name=None,
            external_account_email=None,
            server_url=None,
            scopes=["users:read"],
            capabilities=[],
            encrypted_data={"access_token": "secret"},
            extra_metadata={},
            status="active",
            expires_at=None,
            last_verified_at=now,
            created_at=now,
            updated_at=now,
        )

        with patch(
            "catchup.server.workflow_credentials.api.WorkflowCredentialService"
        ) as service_cls:
            service_cls.return_value.list_for_user.return_value = [credential]
            response = self.client.get("/api/v1/workflow-credentials")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("encrypted_data", payload["items"][0])
        self.assertEqual(payload["items"][0]["vendor"], "slack")

    def test_delete_returns_not_found_for_unowned_credential(self) -> None:
        with patch(
            "catchup.server.workflow_credentials.api.WorkflowCredentialService"
        ) as service_cls:
            service_cls.return_value.delete_for_user.return_value = False
            response = self.client.delete("/api/v1/workflow-credentials/123")

        self.assertEqual(response.status_code, 404)

    def test_authorize_requires_workspace_membership_and_sanitizes_redirect(self) -> None:
        self.db.scalar.return_value = object()
        stored_payloads = []

        async def store_state(**kwargs):
            stored_payloads.append(kwargs)

        service = SimpleNamespace(
            get_user_authorization_url=lambda state: f"https://slack.com/oauth?state={state}"
        )

        with (
            patch(
                "catchup.server.workflow_credentials.api.store_oauth_state_payload",
                store_state,
            ),
            patch(
                "catchup.server.workflow_credentials.api.get_slack_oauth_service",
                return_value=service,
            ),
            patch(
                "catchup.server.workflow_credentials.api.ensure_workflow_credential_encryption_ready",
            ),
            patch(
                "catchup.server.workflow_credentials.api.SessionLocal",
                self.db_session,
            ),
        ):
            response = self.client.get(
                "/api/v1/workflow-credentials/slack/oauth/authorize",
                params={
                    "workspace_id": "2",
                    "redirect_after": "https://evil.example/callback",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 307)
        self.assertIn("https://slack.com/oauth", response.headers["location"])
        payload = stored_payloads[0]["payload"]
        self.assertEqual(payload["purpose"], "workflow_personal")
        self.assertEqual(payload["workspace_id"], 2)
        self.assertEqual(payload["redirect_after"], "/settings/credentials")

    def test_authorize_fails_before_consent_when_encryption_key_is_missing(self) -> None:
        self.db.scalar.return_value = object()

        with patch(
            "catchup.server.workflow_credentials.api.ensure_workflow_credential_encryption_ready",
            side_effect=CredentialCryptoError("missing key"),
        ), patch(
            "catchup.server.workflow_credentials.api.SessionLocal",
            self.db_session,
        ):
            response = self.client.get(
                "/api/v1/workflow-credentials/slack/oauth/authorize",
                params={"workspace_id": "2"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 503)

    def test_authorize_rejects_non_member_workspace(self) -> None:
        self.db.scalar.return_value = None

        with patch(
            "catchup.server.workflow_credentials.api.SessionLocal",
            self.db_session,
        ):
            response = self.client.get(
                "/api/v1/workflow-credentials/github/oauth/authorize",
                params={"workspace_id": "2"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 403)
