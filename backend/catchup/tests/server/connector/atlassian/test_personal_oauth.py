from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from catchup.connectors.atlassian.callback_service import CallbackResult
from catchup.server.connector.atlassian import auth_api


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _context() -> SimpleNamespace:
    resource = SimpleNamespace(
        id="cloud-1",
        name="Site",
        url="https://site.atlassian.net",
        avatar_url=None,
    )
    return SimpleNamespace(
        tokens=SimpleNamespace(
            access_token="atlassian-access",
            refresh_token="atlassian-refresh",
            token_type="Bearer",
            expires_in=3600,
        ),
        user_info=SimpleNamespace(
            account_id="account-1",
            name="Jane",
            email="jane@example.com",
        ),
        resources=[resource],
        aggregated_scopes={"cloud-1": {"read:me", "read:jira-work"}},
        expires_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )


def _multi_resource_context() -> SimpleNamespace:
    first = SimpleNamespace(
        id="cloud-1",
        name="Site 1",
        url="https://site-1.atlassian.net",
        avatar_url=None,
    )
    second = SimpleNamespace(
        id="cloud-2",
        name="Site 2",
        url="https://site-2.atlassian.net",
        avatar_url="https://avatar.example/site-2.png",
    )
    context = _context()
    context.resources = [first, second]
    context.aggregated_scopes = {
        "cloud-1": {"read:jira-work", "read:me"},
        "cloud-2": {"read:confluence-content.summary", "read:me"},
    }
    return context


class AtlassianPersonalOAuthTests(IsolatedAsyncioTestCase):
    def test_personal_oauth_request_stores_atlassian_grant_as_one_credential(self) -> None:
        request = auth_api._build_atlassian_personal_oauth_request(
            _multi_resource_context(),
            {"workspace_id": 2, "user_id": 7},
        )

        self.assertEqual(request.external_tenant_id, "atlassian")
        self.assertEqual(request.external_account_id, "account-1")
        self.assertEqual(
            request.scopes,
            [
                "read:confluence-content.summary",
                "read:jira-work",
                "read:me",
            ],
        )
        self.assertEqual(len(request.extra_metadata["resources"]), 2)
        self.assertEqual(request.token_payload["resources"][1]["id"], "cloud-2")

    async def test_sync_install_branch_preserves_existing_followups(self) -> None:
        callback_service = SimpleNamespace(
            collect_oauth_context=AsyncMock(return_value=_context()),
            persist_sync_context=AsyncMock(
                return_value=CallbackResult(
                    resources=_context().resources,
                    confluence_targets=[],
                    jira_targets=["cloud-1"],
                )
            ),
        )
        background_tasks = Mock()

        with (
            patch(
                "catchup.server.connector.atlassian.auth_api.consume_oauth_state_payload",
                AsyncMock(return_value={"purpose": "sync_install", "vendor": "atlassian"}),
            ),
            patch(
                "catchup.server.connector.atlassian.auth_api.AtlassianCallbackService",
                return_value=callback_service,
            ),
            patch(
                "catchup.server.connector.atlassian.auth_api._register_atlassian_knowledge_sources",
                AsyncMock(),
            ) as register_sources,
            patch(
                "catchup.server.connector.atlassian.auth_api._schedule_atlassian_followups",
            ) as schedule_followups,
        ):
            result = await auth_api._handle_atlassian_oauth_callback.__wrapped__(
                provider="atlassian",
                code="code",
                background_tasks=background_tasks,
                state="state",
                error=None,
                atlassian_service=Mock(),
            )

        callback_service.persist_sync_context.assert_awaited_once()
        register_sources.assert_awaited_once()
        schedule_followups.assert_called_once()
        self.assertIn("atlassian_installed=true", result)

    async def test_workflow_personal_branch_persists_without_sync_followups(self) -> None:
        callback_service = SimpleNamespace(
            collect_oauth_context=AsyncMock(return_value=_context()),
            persist_sync_context=AsyncMock(),
        )
        background_tasks = Mock()

        with (
            patch(
                "catchup.server.connector.atlassian.auth_api.consume_oauth_state_payload",
                AsyncMock(
                    return_value={
                        "purpose": "workflow_personal",
                        "vendor": "atlassian",
                        "user_id": 7,
                        "workspace_id": 2,
                        "redirect_after": "/settings/credentials",
                    }
                ),
            ),
            patch(
                "catchup.server.connector.atlassian.auth_api.AtlassianCallbackService",
                return_value=callback_service,
            ),
            patch(
                "catchup.server.connector.atlassian.auth_api.run_in_threadpool",
                _run_immediately,
            ),
            patch(
                "catchup.server.connector.atlassian.auth_api._persist_atlassian_workflow_credentials_db",
            ) as persist_credential,
            patch(
                "catchup.server.connector.atlassian.auth_api._schedule_atlassian_followups",
            ) as schedule_followups,
        ):
            result = await auth_api._handle_atlassian_oauth_callback.__wrapped__(
                provider="atlassian",
                code="code",
                background_tasks=background_tasks,
                state="state",
                error=None,
                atlassian_service=Mock(),
            )

        callback_service.persist_sync_context.assert_not_called()
        persist_credential.assert_called_once()
        schedule_followups.assert_not_called()
        self.assertIn("credential_connected=true", result)

    async def test_workflow_error_consumes_state_for_completion_redirect(self) -> None:
        with patch(
            "catchup.server.connector.atlassian.auth_api.consume_workflow_redirect_after",
            AsyncMock(
                return_value="/settings/credentials",
            ),
        ):
            with self.assertRaises(auth_api.AtlassianWorkflowCallbackError) as caught:
                await auth_api._handle_atlassian_oauth_callback.__wrapped__(
                    provider="atlassian",
                    code=None,
                    background_tasks=Mock(),
                    state="state",
                    error="access_denied",
                    atlassian_service=Mock(),
                )

        self.assertEqual(caught.exception.redirect_after, "/settings/credentials")
