from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.db.models import GithubInstallationType
from catchup.sync.ingestion.services.github import GithubIngestionService
from catchup.sync.ingestion.services.github import GithubRepoRef


def _make_service() -> tuple[GithubIngestionService, SimpleNamespace]:
    repository = SimpleNamespace(
        delete_documents=AsyncMock(),
        upsert_documents=AsyncMock(return_value=[]),
    )

    with patch(
        "catchup.sync.ingestion.services.github.GitHubApiClient",
        return_value=SimpleNamespace(),
    ):
        service = GithubIngestionService(
            repository=repository,
            installation_id=123,
            access_token="token",
            account_login="octo-org",
            account_type=GithubInstallationType.ORGANIZATION,
            enable_summarization=False,
        )

    return service, repository


class GithubIngestionServiceIncrementalSyncTests(IsolatedAsyncioTestCase):
    async def test_issue_incremental_sync_fetches_only_claimed_issue(self) -> None:
        service, repository = _make_service()
        audit_context = SimpleNamespace(trace_id="audit-issue")
        document = Document(
            id="github:issue:octo-org/octo-repo:123",
            page_content="refreshed issue",
            metadata={"entity_type": "issue"},
        )
        issue_nodes = [("123", {"number": 123})]

        with (
            patch.object(
                service,
                "_get_repo_ref",
                AsyncMock(
                    return_value=GithubRepoRef(
                        repo_id=42,
                        full_name="octo-org/octo-repo",
                        owner="octo-org",
                        repo="octo-repo",
                    )
                ),
            ),
            patch.object(service, "_sync_issues", AsyncMock()) as sync_issues,
            patch.object(service, "_sync_pull_requests", AsyncMock()) as sync_pull_requests,
            patch.object(
                service,
                "_fetch_issue_nodes",
                AsyncMock(return_value=(issue_nodes, [])),
            ) as fetch_issue_nodes,
            patch.object(
                service,
                "_build_issue_documents_sync",
                Mock(return_value=([document], [])),
            ) as build_issue_documents,
        ):
            result = await service.incremental_sync(
                repo_id=42,
                record_type="issue",
                record_id="123",
                event_kind="updated",
                since=datetime(2026, 5, 16, tzinfo=timezone.utc),
                audit_context=audit_context,
            )

        fetch_issue_nodes.assert_awaited_once_with(
            owner="octo-org",
            repo="octo-repo",
            issue_ids=["123"],
        )
        build_issue_documents.assert_called_once_with(
            "octo-org",
            "octo-repo",
            issue_nodes,
        )
        sync_issues.assert_not_awaited()
        sync_pull_requests.assert_not_awaited()
        repository.upsert_documents.assert_awaited_once()

        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[0], [document])
        self.assertEqual(upsert_call.args[1], [document.id])
        self.assertIs(upsert_call.kwargs["audit_context"], audit_context)
        self.assertIn("mode=incremental_exact", upsert_call.kwargs["context"])
        self.assertEqual(result, {"synced": 1, "errors": 0, "skipped": False})

    async def test_pull_request_incremental_sync_fetches_only_claimed_pull_request(self) -> None:
        service, repository = _make_service()
        audit_context = SimpleNamespace(trace_id="audit-pr")
        document = Document(
            id="github:pr:octo-org/octo-repo:456",
            page_content="refreshed pull request",
            metadata={"entity_type": "pull_request"},
        )
        pull_request_nodes = [("456", {"number": 456})]

        with (
            patch.object(
                service,
                "_get_repo_ref",
                AsyncMock(
                    return_value=GithubRepoRef(
                        repo_id=42,
                        full_name="octo-org/octo-repo",
                        owner="octo-org",
                        repo="octo-repo",
                    )
                ),
            ),
            patch.object(service, "_sync_issues", AsyncMock()) as sync_issues,
            patch.object(service, "_sync_pull_requests", AsyncMock()) as sync_pull_requests,
            patch.object(
                service,
                "_fetch_pull_request_nodes",
                AsyncMock(return_value=(pull_request_nodes, [])),
            ) as fetch_pull_request_nodes,
            patch.object(
                service,
                "_build_pull_request_documents_sync",
                Mock(return_value=([document], [])),
            ) as build_pull_request_documents,
        ):
            result = await service.incremental_sync(
                repo_id=42,
                record_type="pull_request",
                record_id="456",
                event_kind="updated",
                since=datetime(2026, 5, 16, tzinfo=timezone.utc),
                audit_context=audit_context,
            )

        fetch_pull_request_nodes.assert_awaited_once_with(
            owner="octo-org",
            repo="octo-repo",
            pull_request_ids=["456"],
        )
        build_pull_request_documents.assert_called_once_with(
            "octo-org",
            "octo-repo",
            pull_request_nodes,
        )
        sync_issues.assert_not_awaited()
        sync_pull_requests.assert_not_awaited()
        repository.upsert_documents.assert_awaited_once()

        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[0], [document])
        self.assertEqual(upsert_call.args[1], [document.id])
        self.assertIs(upsert_call.kwargs["audit_context"], audit_context)
        self.assertIn("mode=incremental_exact", upsert_call.kwargs["context"])
        self.assertEqual(result, {"synced": 1, "errors": 0, "skipped": False})
