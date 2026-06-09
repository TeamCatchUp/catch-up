from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from langchain_core.documents import Document

from catchup.connectors.github.client import GitHubApiClient
from catchup.sync.ingestion.adapters.confluence import (
    ConfluenceSpaceFullSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.confluence import (
    ConfluenceSpaceIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.confluence import ConfluenceSpaceSyncAdapter
from catchup.sync.ingestion.adapters.github import (
    GithubRepositoryFullSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.github import (
    GithubRepositoryIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.github import GithubRepositorySyncAdapter
from catchup.sync.ingestion.adapters.github.repository_sync import (
    GithubRepositoryPersistResult,
)
from catchup.sync.ingestion.adapters.github.repository_sync import (
    GithubRepositorySummaryResult,
)
from catchup.sync.ingestion.adapters.github.repository_sync import (
    GithubRepositoryTransformResult,
)
from catchup.sync.ingestion.adapters.slack import (
    SlackMessageIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.slack import SlackMessageSyncAdapter
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow


def _window() -> SyncWindow:
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


class MigratedConnectorDescriptorTests(IsolatedAsyncioTestCase):
    async def test_slack_deleted_incremental_result_reports_deleted_count(self) -> None:
        repository = SimpleNamespace(delete_documents=AsyncMock())
        service = SimpleNamespace(repository=repository)
        adapter = SlackMessageSyncAdapter(service=service)
        execution = SlackMessageIncrementalSyncExecutionRequest(
            tenant_id="T123",
            channel_id="C123",
            record_id="1711.0001",
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

        self.assertEqual(persisted.persisted_count, 0)
        self.assertEqual(persisted.deleted_count, 1)
        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )

    async def test_github_deleted_incremental_result_reports_deleted_count(self) -> None:
        repository = SimpleNamespace(delete_documents=AsyncMock())

        async def get_repo_ref(_repo_id):
            return SimpleNamespace(owner="org", repo="repo", full_name="org/repo")

        service = SimpleNamespace(repository=repository, _get_repo_ref=get_repo_ref)
        adapter = GithubRepositorySyncAdapter(service=service)
        execution = GithubRepositoryIncrementalSyncExecutionRequest(
            tenant_id="123",
            repo_id=456,
            record_type="issue",
            record_id="7",
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

        self.assertEqual(persisted.persisted_count, 0)
        self.assertEqual(persisted.deleted_count, 1)
        repository.delete_documents.assert_awaited_once_with(["github:issue:org/repo:7"])

    async def test_github_full_sync_batch_persists_transformed_documents(self) -> None:
        repository = SimpleNamespace(upsert_documents=AsyncMock())
        service = SimpleNamespace(summarizer=None, repository=repository)

        def build_issue_batch_documents_sync(_owner, _repo, _records):
            document = Document(id="github:issue:org/repo:7", page_content="issue")
            return [document], [document.id], 0

        service._build_issue_batch_documents_sync = build_issue_batch_documents_sync
        adapter = GithubRepositorySyncAdapter(service=service)
        execution = GithubRepositoryFullSyncExecutionRequest(
            tenant_id="123",
            repo_id=456,
            repo_full_name="org/repo",
            owner="org",
            repo="repo",
            record_type="issue",
            records=({"number": 7},),
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

        repository.upsert_documents.assert_awaited_once()
        self.assertEqual(persisted.persisted_count, 1)
        self.assertEqual(persisted.error_count, 0)

    async def test_github_full_sync_page_fetch_exposes_cursor_contract(self) -> None:
        client = SimpleNamespace(
            fetch_issues_graphql_page=AsyncMock(
                return_value=SimpleNamespace(
                    nodes=({"number": 7},),
                    next_cursor="cursor-2",
                    is_last=False,
                    stopped_by_since=False,
                )
            )
        )
        service = SimpleNamespace(client=client, _start_sync=lambda *_args: None)
        adapter = GithubRepositorySyncAdapter(service=service)
        execution = GithubRepositoryFullSyncExecutionRequest(
            tenant_id="123",
            repo_id=456,
            repo_full_name="org/repo",
            owner="org",
            repo="repo",
            record_type="issue",
            batch_index=1,
            after_cursor="cursor-1",
            sync_from_dt=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

        fetched = await adapter.fetch(execution=execution, sync_window=_window())
        result = adapter.build_result(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
            transformed=GithubRepositoryTransformResult(),
            summary=GithubRepositorySummaryResult(),
            persisted=GithubRepositoryPersistResult(
                persisted_count=1,
                deleted_count=0,
                error_count=0,
                skipped=False,
            ),
        )

        client.fetch_issues_graphql_page.assert_awaited_once_with(
            owner="org",
            repo="repo",
            after_cursor="cursor-1",
            since=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(fetched.records, ({"number": 7},))
        self.assertFalse(fetched.is_last)
        self.assertEqual(fetched.next_cursor, "cursor-2")
        self.assertFalse(fetched.stopped_by_since)
        self.assertEqual(result.metadata["next_cursor"], "cursor-2")
        self.assertFalse(result.metadata["stopped_by_since"])

    async def test_github_graphql_page_maps_end_cursor_and_since_stop(self) -> None:
        client = GitHubApiClient(access_token="token")
        client._graphql = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "repository": {
                    "issues": {
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "cursor-2",
                        },
                        "nodes": [
                            {
                                "number": 7,
                                "updatedAt": "2026-05-16T00:00:00Z",
                            },
                            {
                                "number": 6,
                                "updatedAt": "2026-04-01T00:00:00Z",
                            },
                        ],
                    }
                }
            }
        )

        page = await client.fetch_issues_graphql_page(
            "org",
            "repo",
            after_cursor="cursor-1",
            since=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(page.nodes, ({"number": 7, "updatedAt": "2026-05-16T00:00:00Z"},))
        self.assertIsNone(page.next_cursor)
        self.assertTrue(page.is_last)
        self.assertTrue(page.stopped_by_since)
        self.assertEqual(client._graphql.await_count, 1)  # type: ignore[attr-defined]
        _, variables = client._graphql.await_args.args  # type: ignore[attr-defined]
        self.assertEqual(
            variables,
            {
                "owner": "org",
                "repo": "repo",
                "first": 50,
                "after": "cursor-1",
            },
        )

    async def test_confluence_deleted_incremental_result_reports_deleted_count(self) -> None:
        repository = SimpleNamespace(delete_by_id_prefix=AsyncMock())

        async def load_space_context(_space_keys):
            return {"ENG": "space-1"}, {"ENG": "Engineering"}, {}

        service = SimpleNamespace(
            cloud_id="cloud-123",
            repository=repository,
            _load_space_sync_context=load_space_context,
        )
        adapter = ConfluenceSpaceSyncAdapter(service=service)
        execution = ConfluenceSpaceIncrementalSyncExecutionRequest(
            tenant_id="cloud-123",
            space_key="ENG",
            record_type="page",
            record_id="1001",
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

        self.assertEqual(persisted.persisted_count, 0)
        self.assertEqual(persisted.deleted_count, 1)
        repository.delete_by_id_prefix.assert_awaited_once_with(
            "confluence:page:1001:chunk:"
        )

    async def test_confluence_full_sync_batch_persists_transformed_items(self) -> None:
        stored: list[dict[str, object]] = []

        async def process_page(content, **_kwargs):
            return ConfluenceTransformResult(
                documents=[
                    Document(
                        id=f"confluence:page:{content.id}:chunk:0",
                        page_content="page",
                    )
                ],
                embed_inputs=[],
            )

        async def store_transform_result(**kwargs):
            stored.append(kwargs)

        service = SimpleNamespace(
            cloud_id="cloud-123",
            _process_page=process_page,
            _store_transform_result=store_transform_result,
            _is_retryable_connector_error=lambda _exc: False,
        )
        adapter = ConfluenceSpaceSyncAdapter(service=service)
        execution = ConfluenceSpaceFullSyncExecutionRequest(
            tenant_id="cloud-123",
            space_key="ENG",
            space_id="space-1",
            record_type="page",
            records=(
                {
                    "id": "1001",
                    "status": "current",
                    "title": "Page",
                    "version": {
                        "number": 1,
                        "createdAt": "2026-05-16T00:00:00.000Z",
                    },
                },
            ),
            sync_from_dt=datetime(2026, 5, 1, tzinfo=timezone.utc),
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

        self.assertEqual(persisted.persisted_count, 1)
        self.assertEqual(persisted.error_count, 0)
        self.assertEqual(stored[0]["entity_type"], "page")
        self.assertEqual(stored[0]["content_id"], "1001")
