from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from langchain_core.documents import Document

from catchup.connector_core.adapters.jira import JiraIssueFullSyncAdapter
from catchup.connector_core.adapters.jira import JiraIssueFullSyncExecutionRequest
from catchup.connector_core.adapters.jira import JiraIssueIncrementalAdapter
from catchup.connector_core.adapters.jira import (
    JiraIssueIncrementalSyncExecutionRequest,
)
from catchup.connector_core.adapters.jira.issue_dependencies import (
    JiraIssueIngestionDependencies,
)
from catchup.connector_core.ports.sync_ingestion import SyncWindow


class _FakeClient:
    def __init__(self) -> None:
        self.search_calls: list[dict] = []
        self.get_issue_calls: list[str] = []

    async def search_issues(self, **kwargs):
        self.search_calls.append(kwargs)
        return {
            "issues": [{"key": "GRT-1", "id": "10001", "fields": {}}],
            "isLast": False,
            "nextPageToken": "next-token",
        }

    async def get_issue(self, issue_key: str):
        self.get_issue_calls.append(issue_key)
        return {"key": issue_key, "id": "10001", "fields": {}}


class _FakeTransformer:
    def transform_issue(self, issue_data, site_url):
        issue_key = issue_data["key"]
        return Document(
            id=f"jira:issue:{issue_key}",
            page_content=f"{site_url}:{issue_key}",
            metadata={
                "source": "jira",
                "entity_type": "issue",
                "issue_key": issue_key,
                "project_key": "GRT",
                "contextual_content": issue_key,
            },
        )


class _FakeRepository:
    def __init__(self) -> None:
        self.upsert_calls: list[dict] = []
        self.delete_calls: list[list[str]] = []

    async def upsert_documents(self, documents, ids, audit_context=None, context=None):
        self.upsert_calls.append(
            {
                "documents": documents,
                "ids": ids,
                "audit_context": audit_context,
                "context": context,
            }
        )
        return ids

    async def delete_documents(self, ids):
        self.delete_calls.append(ids)


def _window() -> SyncWindow:
    return SyncWindow(
        window_start=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 8, 5, 16, tzinfo=timezone.utc),
    )


def _dependencies(client: _FakeClient, repository: _FakeRepository):
    return JiraIssueIngestionDependencies(
        cloud_id="cloud-1",
        site_url="https://example.atlassian.net",
        client=client,
        field_mapper=SimpleNamespace(),
        transformer=_FakeTransformer(),
        repository=repository,
        summarizer=None,
    )


class JiraIssueIngestionAdapterTests(IsolatedAsyncioTestCase):
    async def test_full_sync_fetches_one_jira_search_page(self) -> None:
        client = _FakeClient()
        repository = _FakeRepository()
        adapter = JiraIssueFullSyncAdapter(
            dependencies=_dependencies(client, repository),
        )

        result = await adapter.fetch(
            execution=JiraIssueFullSyncExecutionRequest(
                tenant_id="cloud-1",
                project_key="GRT",
                batch_index=2,
                next_page_token="cursor-1",
                max_results=43,
            ),
            sync_window=_window(),
        )

        self.assertEqual(result.fetched_count, 1)
        self.assertFalse(result.is_last)
        self.assertEqual(result.next_page_token, "next-token")
        self.assertEqual(client.search_calls[0]["next_page_token"], "cursor-1")
        self.assertEqual(client.search_calls[0]["max_results"], 43)
        self.assertEqual(
            client.search_calls[0]["jql"],
            'updated >= "2026-05-08 05:00" AND project = "GRT" ORDER BY updated DESC',
        )

    async def test_incremental_fetches_exact_issue_instead_of_project_jql(self) -> None:
        client = _FakeClient()
        repository = _FakeRepository()
        adapter = JiraIssueIncrementalAdapter(
            dependencies=_dependencies(client, repository),
        )

        fetched = await adapter.fetch(
            execution=JiraIssueIncrementalSyncExecutionRequest(
                tenant_id="cloud-1",
                project_key="GRT",
                issue_key="GRT-1",
                event_kind="updated",
            ),
            sync_window=_window(),
        )

        self.assertEqual(fetched.fetched_record_ids, ("GRT-1",))
        self.assertFalse(hasattr(fetched, "batch_index"))
        self.assertFalse(hasattr(fetched, "next_page_token"))
        self.assertEqual(client.get_issue_calls, ["GRT-1"])
        self.assertEqual(client.search_calls, [])

    async def test_incremental_delete_deletes_issue_document_id(self) -> None:
        client = _FakeClient()
        repository = _FakeRepository()
        adapter = JiraIssueIncrementalAdapter(
            dependencies=_dependencies(client, repository),
        )
        execution = JiraIssueIncrementalSyncExecutionRequest(
            tenant_id="cloud-1",
            project_key="GRT",
            issue_key="GRT-1",
            event_kind="deleted",
        )

        fetched = await adapter.fetch(execution=execution, sync_window=_window())
        transformed = await adapter.transform(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        self.assertEqual(client.get_issue_calls, [])
        self.assertEqual(repository.delete_calls, [["jira:issue:GRT-1"]])
        self.assertEqual(persisted.deleted_count, 1)
