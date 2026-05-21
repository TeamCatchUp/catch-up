from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.connectors.jira.service import JiraIngestionService


def _make_service() -> tuple[JiraIngestionService, SimpleNamespace]:
    repository = SimpleNamespace(
        delete_documents=AsyncMock(),
        upsert_documents=AsyncMock(return_value=[]),
        ensure_initialized=Mock(),
    )

    with patch(
        "catchup.connectors.jira.service.JiraApiClient",
        return_value=SimpleNamespace(),
    ):
        service = JiraIngestionService(
            repository=repository,
            cloud_id="cloud-1",
            token_provider=SimpleNamespace(),
            site_url="https://example.atlassian.net",
            enable_summarization=False,
        )

    service._initialized = True
    service.transformer = SimpleNamespace(
        project_cache={},
        sprint_cache={},
        transform_issue=Mock(
            return_value=Document(
                id="jira:issue:GRT-1",
                page_content="refreshed issue",
                metadata={"entity_type": "issue"},
            )
        ),
    )
    return service, repository


class JiraIngestionServiceIncrementalSyncTests(IsolatedAsyncioTestCase):
    async def test_incremental_sync_fetches_only_claimed_issue(self) -> None:
        service, repository = _make_service()
        audit_context = SimpleNamespace(trace_id="audit-jira")
        service.client = SimpleNamespace(
            get_issue=AsyncMock(
                return_value={
                    "id": "10001",
                    "key": "GRT-1",
                    "fields": {"issuetype": {"name": "Task"}},
                }
            )
        )

        with (
            patch.object(
                service,
                "_load_project_sync_context",
                AsyncMock(return_value=({"GRT": SimpleNamespace()}, {1: SimpleNamespace()})),
            ) as load_project_context,
            patch.object(
                service,
                "_sync_project_issues",
                AsyncMock(
                    side_effect=AssertionError(
                        "incremental issue sync must not call broad project sync"
                    )
                ),
            ) as sync_project_issues,
        ):
            result = await service.incremental_sync(
                project_key="GRT",
                record_id="GRT-1",
                event_kind="updated",
                since=datetime(2026, 5, 16, tzinfo=timezone.utc),
                audit_context=audit_context,
            )

        load_project_context.assert_awaited_once_with("GRT")
        service.client.get_issue.assert_awaited_once_with("GRT-1")
        service.transformer.transform_issue.assert_called_once()
        sync_project_issues.assert_not_awaited()
        repository.upsert_documents.assert_awaited_once()

        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[1], ["jira:issue:GRT-1"])
        self.assertIs(upsert_call.kwargs["audit_context"], audit_context)
        self.assertIn("mode=incremental_exact", upsert_call.kwargs["context"])
        self.assertEqual(result, {"synced": 1, "errors": 0, "skipped": False})
