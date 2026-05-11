from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from catchup.connectors.slack.auth import SlackOAuthService
from catchup.server.connector.slack import auth_api


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _tokens() -> SimpleNamespace:
    return SimpleNamespace(
        team=SimpleNamespace(id="T123", name="Team"),
        authed_user=SimpleNamespace(
            id="U123",
            access_token="xoxp-user",
            scope="users:read,team:read",
            token_type="user",
            refresh_token="xoxe-refresh",
            expires_in=3600,
        ),
        app_id="A123",
        access_token="xoxb-bot",
        scope="channels:read",
        bot_user_id="B123",
        refresh_token=None,
        expires_in=None,
        incoming_webhook=None,
    )


class SlackPersonalOAuthTests(IsolatedAsyncioTestCase):
    def test_user_only_token_response_parses_for_workflow_oauth(self) -> None:
        tokens = SlackOAuthService()._parse_token_response(
            {
                "ok": True,
                "app_id": "A123",
                "team": {"id": "T123", "name": "Team"},
                "authed_user": {
                    "id": "U123",
                    "access_token": "xoxp-user",
                    "scope": "users:read,team:read",
                    "token_type": "user",
                    "expires_in": 3600,
                },
            }
        )

        self.assertIsNone(tokens.access_token)
        self.assertEqual(tokens.authed_user.access_token, "xoxp-user")

    async def test_sync_install_branch_preserves_existing_followups(self) -> None:
        slack_service = SimpleNamespace(exchange_code_for_tokens=AsyncMock(return_value=_tokens()))
        background_tasks = Mock()

        with (
            patch(
                "catchup.server.connector.slack.auth_api.consume_oauth_state_payload",
                AsyncMock(return_value={"purpose": "sync_install", "vendor": "slack"}),
            ),
            patch(
                "catchup.server.connector.slack.auth_api._persist_slack_installation",
                AsyncMock(),
            ) as persist_installation,
            patch(
                "catchup.server.connector.slack.auth_api._schedule_slack_followups",
            ) as schedule_followups,
        ):
            result = await auth_api._handle_slack_oauth_callback.__wrapped__(
                provider="slack",
                code="code",
                state="state",
                error=None,
                slack_service=slack_service,
                background_tasks=background_tasks,
            )

        persist_installation.assert_awaited_once()
        schedule_followups.assert_called_once_with(background_tasks, "T123")
        self.assertIn("slack_installed=true", result)

    async def test_workflow_personal_branch_persists_credential_without_followups(self) -> None:
        slack_service = SimpleNamespace(exchange_code_for_tokens=AsyncMock(return_value=_tokens()))
        background_tasks = Mock()

        with (
            patch(
                "catchup.server.connector.slack.auth_api.consume_oauth_state_payload",
                AsyncMock(
                    return_value={
                        "purpose": "workflow_personal",
                        "vendor": "slack",
                        "user_id": 7,
                        "workspace_id": 2,
                        "redirect_after": "/settings/credentials?tab=oauth",
                    }
                ),
            ),
            patch(
                "catchup.server.connector.slack.auth_api.run_in_threadpool",
                _run_immediately,
            ),
            patch(
                "catchup.server.connector.slack.auth_api._persist_slack_workflow_credential_db",
            ) as persist_credential,
            patch(
                "catchup.server.connector.slack.auth_api._schedule_slack_followups",
            ) as schedule_followups,
        ):
            result = await auth_api._handle_slack_oauth_callback.__wrapped__(
                provider="slack",
                code="code",
                state="state",
                error=None,
                slack_service=slack_service,
                background_tasks=background_tasks,
            )

        persist_credential.assert_called_once()
        schedule_followups.assert_not_called()
        self.assertIn("credential_connected=true", result)
        self.assertIn("tab=oauth", result)

    async def test_workflow_error_consumes_state_for_completion_redirect(self) -> None:
        with patch(
            "catchup.server.connector.slack.auth_api.consume_workflow_redirect_after",
            AsyncMock(
                return_value="/settings/credentials",
            ),
        ):
            with self.assertRaises(auth_api.SlackCallbackError) as caught:
                await auth_api._handle_slack_oauth_callback.__wrapped__(
                    provider="slack",
                    code=None,
                    state="state",
                    error="access_denied",
                    slack_service=SimpleNamespace(),
                    background_tasks=Mock(),
                )

        self.assertEqual(caught.exception.redirect_after, "/settings/credentials")
