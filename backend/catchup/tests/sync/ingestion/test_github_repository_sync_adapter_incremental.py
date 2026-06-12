from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubUser
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.adapters.github import (
    GithubRepositoryIncrementalSyncAdapter,
)
from catchup.sync.ingestion.adapters.github import (
    GithubRepositoryIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.github.repository_models import GithubRepoRef
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryFetchResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositorySummaryResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow


def _window() -> SyncWindow:
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _make_adapter(
    pr_v2_vector_store: SimpleNamespace | None = None,
) -> tuple[GithubRepositoryIncrementalSyncAdapter, SimpleNamespace]:
    repository = SimpleNamespace(
        delete_documents=AsyncMock(),
        generate_embeddings=AsyncMock(return_value=[[0.0123, -0.0456, 0.0789]]),
        store_with_embeddings=AsyncMock(
            return_value=["github:pr:octo-org/octo-repo:456"]
        ),
        upsert_documents=AsyncMock(return_value=[]),
    )

    adapter = GithubRepositoryIncrementalSyncAdapter(
        installation_id=123,
        client=SimpleNamespace(),
        repository=repository,
        pr_v2_vector_store=pr_v2_vector_store,
    )
    return adapter, repository


def _audit_context() -> SyncAuditContext:
    return SyncAuditContext(
        connector=SyncConnector.GITHUB,
        scope_id="123",
        target_id="42",
        job_id="job-1",
        task_id="task-1",
    )


def _make_pr_document(
    *,
    synced_at: str = "2026-06-10T03:00:00+00:00",
) -> Document:
    return Document(
        id="github:pr:octo-org/octo-repo:456",
        page_content="summarized pull request",
        metadata={
            "entity_type": "pr",
            "synced_at": synced_at,
        },
    )


def _make_pull_request() -> GithubPullRequest:
    return GithubPullRequest(
        number=456,
        url="https://api.github.com/repos/octo-org/octo-repo/pulls/456",
        html_url="https://github.com/octo-org/octo-repo/pull/456",
        title="Improve sync",
        body="Sync PRs into v2",
        state="open",
        merged=False,
        base_ref="main",
        head_ref="feature/pr-v2",
        author=GithubUser(id=1, login="octocat", name="Octo Cat"),
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        changed_files=2,
    )


class GithubRepositoryIncrementalSyncAdapterTests(IsolatedAsyncioTestCase):
    async def test_issue_incremental_sync_fetches_only_claimed_issue(self) -> None:
        adapter, repository = _make_adapter()
        audit_context = _audit_context()
        document = Document(
            id="github:issue:octo-org/octo-repo:123",
            page_content="refreshed issue",
            metadata={"entity_type": "issue"},
        )
        issue_nodes = [("123", {"number": 123})]

        with (
            patch.object(
                adapter,
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
            patch.object(
                adapter,
                "_fetch_issue_nodes",
                AsyncMock(return_value=(issue_nodes, [])),
            ) as fetch_issue_nodes,
            patch.object(
                adapter,
                "_build_issue_documents_sync",
                Mock(return_value=([document], [])),
            ) as build_issue_documents,
        ):
            execution = GithubRepositoryIncrementalSyncExecutionRequest(
                tenant_id="123",
                repo_id=42,
                record_type="issue",
                record_id="123",
                event_kind="updated",
                since=datetime(2026, 5, 16, tzinfo=timezone.utc),
                audit_context=audit_context,
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
            result = await adapter.persist(
                execution=execution,
                sync_window=_window(),
                transformed=transformed,
                summary=summary,
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
        repository.upsert_documents.assert_awaited_once()

        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[0], [document])
        self.assertEqual(upsert_call.args[1], [document.id])
        self.assertIs(upsert_call.kwargs["audit_context"], audit_context)
        self.assertIn("mode=incremental_exact", upsert_call.kwargs["context"])
        self.assertEqual(result.persisted_count, 1)
        self.assertEqual(result.error_count, 0)

    async def test_pull_request_dual_write_reuses_v1_embedding_for_v2_row(self) -> None:
        pr_v2_vector_store = SimpleNamespace(
            delete=AsyncMock(),
            upsert_documents=AsyncMock(),
        )
        adapter, repository = _make_adapter(pr_v2_vector_store=pr_v2_vector_store)
        v1_document = _make_pr_document()
        v2_document = adapter.pr_v2_mapper.to_document(
            _make_pull_request(),
            owner="octo-org",
            repo="octo-repo",
            installation_id=123,
            content=v1_document.page_content,
            synced_at=datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc),
        )

        result = await adapter._upsert_v1_v2_documents_dual_write(
            v1_documents=[v1_document],
            v2_documents=[v2_document],
            ids=[v1_document.id],
            audit_context=None,
            context="entity_type=pull_request,repo=octo-org/octo-repo",
        )

        self.assertEqual(result.persisted_ids, ["github:pr:octo-org/octo-repo:456"])
        self.assertEqual(result.v2_failed_ids, ())
        repository.generate_embeddings.assert_awaited_once_with(
            [v1_document],
            audit_context=None,
            context="entity_type=pull_request,repo=octo-org/octo-repo",
        )
        repository.delete_documents.assert_awaited_once_with([v1_document.id])
        repository.store_with_embeddings.assert_awaited_once_with(
            [v1_document],
            [[0.0123, -0.0456, 0.0789]],
            [v1_document.id],
            audit_context=None,
            context="entity_type=pull_request,repo=octo-org/octo-repo",
        )
        repository.upsert_documents.assert_not_awaited()
        pr_v2_vector_store.upsert_documents.assert_awaited_once()

        upsert_call = pr_v2_vector_store.upsert_documents.await_args
        v2_document = upsert_call.args[0][0]
        self.assertEqual(v2_document.id, v1_document.id)
        self.assertEqual(v2_document.page_content, "summarized pull request")
        self.assertEqual(upsert_call.kwargs["ids"], [v1_document.id])
        self.assertEqual(upsert_call.kwargs["embeddings"], [[0.0123, -0.0456, 0.0789]])
        self.assertEqual(v2_document.metadata["scope_id"], "123")
        self.assertEqual(v2_document.metadata["title"], "Improve sync")
        self.assertEqual(v2_document.metadata["body"], "Sync PRs into v2")
        self.assertEqual(
            v2_document.metadata["data"]["parts"],
            [{"type": "pr_body", "text": "Sync PRs into v2", "metadata": {}}],
        )
        self.assertNotIn("contextual_content", v2_document.metadata)
        self.assertNotIn("merged", v2_document.metadata["github_pr"])

    async def test_pull_request_v2_upsert_failure_does_not_fail_v1_persist(self) -> None:
        pr_v2_vector_store = SimpleNamespace(
            delete=AsyncMock(),
            upsert_documents=AsyncMock(side_effect=RuntimeError("v2 down")),
        )
        adapter, repository = _make_adapter(pr_v2_vector_store=pr_v2_vector_store)
        v1_document = _make_pr_document()
        v2_document = adapter.pr_v2_mapper.to_document(
            _make_pull_request(),
            owner="octo-org",
            repo="octo-repo",
            installation_id=123,
            content=v1_document.page_content,
            synced_at=datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc),
        )

        result = await adapter._upsert_v1_v2_documents_dual_write(
            v1_documents=[v1_document],
            v2_documents=[v2_document],
            ids=[v1_document.id],
            audit_context=None,
            context="entity_type=pull_request,repo=octo-org/octo-repo",
        )

        self.assertEqual(result.persisted_ids, ["github:pr:octo-org/octo-repo:456"])
        self.assertEqual(result.v2_failed_ids, (v1_document.id,))
        repository.store_with_embeddings.assert_awaited_once()
        pr_v2_vector_store.upsert_documents.assert_awaited_once()

    async def test_pull_request_missing_v2_document_does_not_fail_v1_persist(self) -> None:
        pr_v2_vector_store = SimpleNamespace(
            delete=AsyncMock(),
            upsert_documents=AsyncMock(),
        )
        adapter, repository = _make_adapter(pr_v2_vector_store=pr_v2_vector_store)
        document = _make_pr_document()

        result = await adapter._upsert_v1_v2_documents_dual_write(
            v1_documents=[document],
            v2_documents=[],
            ids=[document.id],
            audit_context=None,
            context="entity_type=pull_request,repo=octo-org/octo-repo",
        )

        self.assertEqual(result.persisted_ids, [])
        self.assertEqual(result.v2_failed_ids, ())
        repository.upsert_documents.assert_awaited_once_with(
            [document],
            [document.id],
            audit_context=None,
            context="entity_type=pull_request,repo=octo-org/octo-repo",
        )
        repository.store_with_embeddings.assert_not_awaited()
        pr_v2_vector_store.upsert_documents.assert_not_awaited()

    async def test_pull_request_delete_removes_v1_and_v2_rows(self) -> None:
        pr_v2_vector_store = SimpleNamespace(
            delete=AsyncMock(),
            upsert_documents=AsyncMock(),
        )
        adapter, repository = _make_adapter(pr_v2_vector_store=pr_v2_vector_store)
        execution = GithubRepositoryIncrementalSyncExecutionRequest(
            tenant_id="123",
            repo_id=42,
            record_type="pull_request",
            record_id="456",
            event_kind="deleted",
        )
        transformed = GithubRepositoryTransformResult(
            owner="octo-org",
            repo="octo-repo",
            repo_full_name="octo-org/octo-repo",
        )

        result = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=GithubRepositorySummaryResult(),
        )

        doc_id = "github:pr:octo-org/octo-repo:456"
        repository.delete_documents.assert_awaited_once_with([doc_id])
        pr_v2_vector_store.delete.assert_awaited_once_with([doc_id])
        self.assertEqual(result.deleted_count, 1)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.v2_error_count, 0)
        self.assertEqual(result.v2_failed_ids, ())

    async def test_pull_request_v2_delete_failure_does_not_fail_v1_delete(self) -> None:
        pr_v2_vector_store = SimpleNamespace(
            delete=AsyncMock(side_effect=RuntimeError("v2 down")),
            upsert_documents=AsyncMock(),
        )
        adapter, repository = _make_adapter(pr_v2_vector_store=pr_v2_vector_store)
        execution = GithubRepositoryIncrementalSyncExecutionRequest(
            tenant_id="123",
            repo_id=42,
            record_type="pull_request",
            record_id="456",
            event_kind="deleted",
        )
        transformed = GithubRepositoryTransformResult(
            owner="octo-org",
            repo="octo-repo",
            repo_full_name="octo-org/octo-repo",
        )

        result = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=GithubRepositorySummaryResult(),
        )

        doc_id = "github:pr:octo-org/octo-repo:456"
        repository.delete_documents.assert_awaited_once_with([doc_id])
        pr_v2_vector_store.delete.assert_awaited_once_with([doc_id])
        self.assertEqual(result.deleted_count, 1)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.v2_error_count, 1)
        self.assertEqual(result.v2_failed_ids, (doc_id,))

        sync_result = adapter.build_result(
            execution=execution,
            sync_window=_window(),
            fetched=GithubRepositoryFetchResult(record_type="pull_request"),
            transformed=transformed,
            summary=GithubRepositorySummaryResult(),
            persisted=result,
        )

        self.assertEqual(sync_result.failed_count, 1)
        self.assertEqual(sync_result.v2_failed_count, 1)
        self.assertEqual(sync_result.v2_failed_ids, (doc_id,))

    async def test_pull_request_incremental_sync_fetches_only_claimed_pull_request(self) -> None:
        adapter, repository = _make_adapter()
        audit_context = _audit_context()
        document = Document(
            id="github:pr:octo-org/octo-repo:456",
            page_content="refreshed pull request",
            metadata={"entity_type": "pull_request"},
        )
        pull_request_nodes = [("456", {"number": 456})]

        with (
            patch.object(
                adapter,
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
            patch.object(
                adapter,
                "_fetch_pull_request_nodes",
                AsyncMock(return_value=(pull_request_nodes, [])),
            ) as fetch_pull_request_nodes,
            patch.object(
                adapter,
                "_build_pull_request_document_bundles_sync",
                Mock(
                    return_value=(
                        [SimpleNamespace(pull_request=SimpleNamespace(), document=document)],
                        [],
                    )
                ),
            ) as build_pull_request_document_bundles,
        ):
            execution = GithubRepositoryIncrementalSyncExecutionRequest(
                tenant_id="123",
                repo_id=42,
                record_type="pull_request",
                record_id="456",
                event_kind="updated",
                since=datetime(2026, 5, 16, tzinfo=timezone.utc),
                audit_context=audit_context,
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
            result = await adapter.persist(
                execution=execution,
                sync_window=_window(),
                transformed=transformed,
                summary=summary,
            )

        fetch_pull_request_nodes.assert_awaited_once_with(
            owner="octo-org",
            repo="octo-repo",
            pull_request_ids=["456"],
        )
        build_pull_request_document_bundles.assert_called_once_with(
            "octo-org",
            "octo-repo",
            pull_request_nodes,
        )
        repository.upsert_documents.assert_awaited_once()

        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[0], [document])
        self.assertEqual(upsert_call.args[1], [document.id])
        self.assertIs(upsert_call.kwargs["audit_context"], audit_context)
        self.assertIn("mode=incremental_exact", upsert_call.kwargs["context"])
        self.assertEqual(result.persisted_count, 1)
        self.assertEqual(result.error_count, 0)

    async def test_pull_request_transform_builds_explicit_v1_and_v2_documents(self) -> None:
        pr_v2_vector_store = SimpleNamespace(
            delete=AsyncMock(),
            upsert_documents=AsyncMock(),
        )
        adapter, _repository = _make_adapter(pr_v2_vector_store=pr_v2_vector_store)
        v1_document = _make_pr_document()
        pull_request = _make_pull_request()
        pull_request_nodes = [("456", {"number": 456})]

        with (
            patch.object(
                adapter,
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
            patch.object(
                adapter,
                "_fetch_pull_request_nodes",
                AsyncMock(return_value=(pull_request_nodes, [])),
            ),
            patch.object(
                adapter,
                "_build_pull_request_document_bundles_sync",
                Mock(
                    return_value=(
                        [SimpleNamespace(pull_request=pull_request, document=v1_document)],
                        [],
                    )
                ),
            ),
        ):
            execution = GithubRepositoryIncrementalSyncExecutionRequest(
                tenant_id="123",
                repo_id=42,
                record_type="pull_request",
                record_id="456",
                event_kind="updated",
            )
            fetched = await adapter.fetch(execution=execution, sync_window=_window())
            transformed = await adapter.transform(
                execution=execution,
                sync_window=_window(),
                fetched=fetched,
            )

        self.assertEqual(transformed.v1_documents, (v1_document,))
        self.assertEqual(transformed.document_ids, (v1_document.id,))
        self.assertEqual(len(transformed.v2_documents), 1)
        self.assertEqual(transformed.v2_documents[0].id, v1_document.id)
        self.assertEqual(
            transformed.v2_documents[0].page_content,
            v1_document.page_content,
        )
        self.assertEqual(transformed.v2_documents[0].metadata["scope_id"], "123")
