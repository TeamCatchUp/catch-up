from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.server.connector.github import auth_api


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


class GitHubPersonalOAuthTests(IsolatedAsyncioTestCase):
    async def test_callback_persists_workflow_credential(self) -> None:
        service = SimpleNamespace(
            exchange_code_for_token=AsyncMock(
                return_value=SimpleNamespace(
                    access_token="ghu-token",
                    token_type="bearer",
                    scope="",
                    expires_in=28800,
                    refresh_token="ghr-refresh",
                    refresh_token_expires_in=15897600,
                )
            ),
            get_authenticated_user=AsyncMock(
                return_value={
                    "id": 123,
                    "login": "octocat",
                    "email": "octo@example.com",
                    "html_url": "https://github.com/octocat",
                }
            ),
            api_url="https://api.github.com",
        )

        with (
            patch(
                "catchup.server.connector.github.auth_api.consume_oauth_state_payload",
                AsyncMock(
                    return_value={
                        "purpose": "workflow_personal",
                        "vendor": "github",
                        "user_id": 7,
                        "workspace_id": 2,
                        "redirect_after": "/settings/credentials",
                    }
                ),
            ),
            patch(
                "catchup.server.connector.github.auth_api.run_in_threadpool",
                _run_immediately,
            ),
            patch(
                "catchup.server.connector.github.auth_api._persist_github_workflow_credential_db",
            ) as persist_credential,
        ):
            response = await auth_api.github_user_oauth_callback(
                code="code",
                state="state",
                github_service=service,
            )

        persist_credential.assert_called_once()
        self.assertIn("credential_connected=true", response.headers["location"])

    async def test_callback_rejects_invalid_state(self) -> None:
        service = SimpleNamespace()

        with patch(
            "catchup.server.connector.github.auth_api.consume_oauth_state_payload",
            AsyncMock(return_value=None),
        ):
            response = await auth_api.github_user_oauth_callback(
                code="code",
                state="bad",
                github_service=service,
            )

        self.assertIn("credential_connected=false", response.headers["location"])
        self.assertIn("reason=invalid_state", response.headers["location"])

    async def test_callback_error_uses_state_redirect_after(self) -> None:
        with patch(
            "catchup.server.connector.github.auth_api.consume_workflow_redirect_after",
            AsyncMock(
                return_value="/settings/credentials?tab=oauth",
            ),
        ):
            response = await auth_api.github_user_oauth_callback(
                code=None,
                state="state",
                error="access_denied",
                github_service=SimpleNamespace(),
            )

        self.assertIn("credential_connected=false", response.headers["location"])
        self.assertIn("tab=oauth", response.headers["location"])
        self.assertIn("reason=access_denied", response.headers["location"])
