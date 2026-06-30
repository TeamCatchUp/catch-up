from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from langchain_core.documents import Document

from catchup.connectors.jira.schemas import JiraIssue
from catchup.connectors.jira.schemas import JiraUser
from catchup.sync.ingestion.adapters.jira import JiraIssueFullSyncAdapter
from catchup.sync.ingestion.adapters.jira import JiraIssueFullSyncExecutionRequest
from catchup.sync.ingestion.adapters.jira import JiraIssueIncrementalAdapter
from catchup.sync.ingestion.adapters.jira import (
    JiraIssueIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillAdapter
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.jira import JiraIssueV2BackfillSeed
from catchup.sync.ingestion.adapters.jira.issue_dependencies import (
    JiraIssueIngestionDependencies,
)
from catchup.sync.ingestion.adapters.jira.issue_v2_document_builder import (
    JiraIssueV2DocumentBuilder,
)
from catchup.sync.ingestion.schemas import SyncWindow


class _FakeClient:
    def __init__(self) -> None:
        self.search_calls: list[dict] = []
        self.get_issue_calls: list[str] = []

    async def search_issues(self, **kwargs):
        self.search_calls.append(kwargs)
        return {
            "issues": [
                {
                    "key": "GRT-1",
                    "id": "10001",
                    "assignee_account_id": "acc-assignee",
                    "fields": {},
                }
            ],
            "isLast": False,
            "nextPageToken": "next-token",
        }

    async def get_issue(self, issue_key: str):
        self.get_issue_calls.append(issue_key)
        return {"key": issue_key, "id": "10001", "fields": {}}


class _FakeTransformer:
    def transform_issue(self, issue_data, site_url):
        issue_key = issue_data["key"]
        record_type = "epic" if issue_data.get("issue_type") == "Epic" else "issue"
        return Document(
            id=f"jira:{record_type}:{issue_key}",
            page_content=f"{site_url}:{issue_key}",
            metadata={
                "source": "jira",
                "entity_type": record_type,
                "issue_key": issue_key,
                "project_key": "GRT",
                "contextual_content": issue_key,
            },
        )

    def parse_issue(self, issue_data, site_url):
        issue_key = issue_data["key"]
        return JiraIssue(
            key=issue_key,
            id=issue_data.get("id", "10001"),
            url=f"{site_url}/browse/{issue_key}",
            project_key="GRT",
            project_name="Growth",
            issue_type=issue_data.get("issue_type", "Task"),
            status="To Do",
            summary=f"Summary {issue_key}",
            description=f"Description {issue_key}",
            assignee=(
                JiraUser(
                    account_id=issue_data.get("assignee_account_id"),
                    display_name="Assignee",
                )
                if issue_data.get("assignee_account_id")
                else None
            ),
            created_at=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 8, 5, 1, tzinfo=timezone.utc),
        )


class _FakeRepository:
    def __init__(self) -> None:
        self.upsert_calls: list[dict] = []
        self.delete_calls: list[list[str]] = []
        self.generate_calls: list[dict] = []
        self.store_calls: list[dict] = []

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

    async def generate_embeddings(self, documents, audit_context=None, context=None):
        self.generate_calls.append(
            {
                "documents": documents,
                "audit_context": audit_context,
                "context": context,
            }
        )
        return [[float(index)] for index, _doc in enumerate(documents, start=1)]

    async def store_with_embeddings(
        self,
        documents,
        embeddings,
        ids,
        audit_context=None,
        context=None,
    ):
        self.store_calls.append(
            {
                "documents": documents,
                "embeddings": embeddings,
                "ids": ids,
                "audit_context": audit_context,
                "context": context,
            }
        )
        return ids


class _FakeVectorStore:
    def __init__(self) -> None:
        self.upsert_calls: list[dict] = []
        self.delete_calls: list[list[str]] = []

    async def upsert_documents(self, documents, ids, embeddings):
        self.upsert_calls.append(
            {"documents": documents, "ids": ids, "embeddings": embeddings}
        )
        return ids

    async def delete(self, ids):
        self.delete_calls.append(ids)


class _FakeV2KnowledgeRepository:
    def __init__(self, missing_metadata_ids: tuple[str, ...] = ()) -> None:
        self.missing_metadata_ids = missing_metadata_ids
        self.metadata_namespace_checks: list[dict] = []

    async def find_missing_metadata_namespace_ids(self, ids, *, namespace):
        self.metadata_namespace_checks.append(
            {"ids": list(ids), "namespace": namespace}
        )
        return self.missing_metadata_ids


class _FakeJiraAssigneeResolver:
    def __init__(
        self,
        mapping: dict[str, str | None] | None = None,
    ) -> None:
        self.mapping = mapping or {
            "acc-assignee": "42",
            "acc-epic": "84",
            "acc-backfill": "126",
        }
        self.account_ids: list[str | None] = []

    def resolve_catchup_user_id(self, db, account_id):
        _ = db
        self.account_ids.append(account_id)
        return self.mapping.get(account_id)


def _window() -> SyncWindow:
    return SyncWindow(
        window_start=datetime(2026, 5, 8, 5, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 8, 5, 16, tzinfo=timezone.utc),
    )


def _dependencies(
    client: _FakeClient,
    repository: _FakeRepository,
    *,
    vector_store: _FakeVectorStore | None = None,
    v2_knowledge_repository: _FakeV2KnowledgeRepository | None = None,
    assignee_resolver: _FakeJiraAssigneeResolver | None = None,
):
    v2_document_builder = None
    if vector_store is not None:
        v2_document_builder = JiraIssueV2DocumentBuilder(
            assignee_resolver=assignee_resolver or _FakeJiraAssigneeResolver(),
            session_factory=lambda: nullcontext(object()),
        )
    return JiraIssueIngestionDependencies(
        cloud_id="cloud-1",
        site_url="https://example.atlassian.net",
        client=client,
        field_mapper=SimpleNamespace(),
        transformer=_FakeTransformer(),
        repository=repository,
        summarizer=None,
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
        v2_document_builder=v2_document_builder,
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
        log_summary = result.connector_log_summary()
        self.assertNotIn("batch_index", log_summary)
        self.assertNotIn("next_page_token_present", log_summary)
        self.assertTrue(log_summary["response_next_page_token_present"])
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
        self.assertEqual(
            repository.delete_calls,
            [["jira:issue:GRT-1", "jira:epic:GRT-1"]],
        )
        self.assertEqual(persisted.deleted_count, 1)

    async def test_full_sync_dual_writes_jira_v2_documents(self) -> None:
        client = _FakeClient()
        repository = _FakeRepository()
        vector_store = _FakeVectorStore()
        assignee_resolver = _FakeJiraAssigneeResolver()
        adapter = JiraIssueFullSyncAdapter(
            dependencies=_dependencies(
                client,
                repository,
                vector_store=vector_store,
                assignee_resolver=assignee_resolver,
            ),
        )
        execution = JiraIssueFullSyncExecutionRequest(
            tenant_id="cloud-1",
            project_key="GRT",
            batch_index=0,
            max_results=50,
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

        self.assertEqual(repository.generate_calls[0]["documents"][0].id, "jira:issue:GRT-1")
        self.assertEqual(
            repository.generate_calls[0]["documents"][0].metadata["cloud_id"],
            "cloud-1",
        )
        self.assertEqual(
            repository.generate_calls[0]["documents"][0].metadata["scope_id"],
            "cloud-1",
        )
        self.assertEqual(repository.delete_calls, [["jira:issue:GRT-1"]])
        self.assertEqual(repository.store_calls[0]["ids"], ["jira:issue:GRT-1"])
        self.assertEqual(
            vector_store.upsert_calls[0]["ids"],
            ["jira:issue:cloud-1:GRT:GRT-1"],
        )
        self.assertEqual(vector_store.upsert_calls[0]["embeddings"], [[1.0]])
        self.assertEqual(
            vector_store.upsert_calls[0]["documents"][0].page_content,
            "https://example.atlassian.net:GRT-1",
        )
        self.assertEqual(
            vector_store.upsert_calls[0]["documents"][0].metadata["internal_author_id"],
            "42",
        )
        self.assertEqual(
            vector_store.upsert_calls[0]["documents"][0]
            .metadata["jira_issue"]["assignee"]["internal_user_id"],
            "42",
        )
        self.assertEqual(assignee_resolver.account_ids, ["acc-assignee"])
        self.assertEqual(persisted.persisted_count, 1)
        self.assertEqual(persisted.v2_error_count, 0)

    async def test_full_sync_dual_writes_jira_epic_v2_documents(self) -> None:
        client = _FakeClient()
        repository = _FakeRepository()
        vector_store = _FakeVectorStore()
        adapter = JiraIssueFullSyncAdapter(
            dependencies=_dependencies(
                client,
                repository,
                vector_store=vector_store,
            ),
        )
        fetched = SimpleNamespace(
            issues=(
                {
                    "key": "GRT-EPIC",
                    "id": "10002",
                    "issue_type": "Epic",
                    "assignee_account_id": "acc-epic",
                },
            )
        )

        transformed = await adapter.transform(
            execution=JiraIssueFullSyncExecutionRequest(
                tenant_id="cloud-1",
                project_key="GRT",
                batch_index=0,
                max_results=50,
            ),
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=JiraIssueFullSyncExecutionRequest(
                tenant_id="cloud-1",
                project_key="GRT",
                batch_index=0,
                max_results=50,
            ),
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=JiraIssueFullSyncExecutionRequest(
                tenant_id="cloud-1",
                project_key="GRT",
                batch_index=0,
                max_results=50,
            ),
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        self.assertEqual(repository.generate_calls[0]["documents"][0].id, "jira:epic:GRT-EPIC")
        self.assertEqual(repository.delete_calls, [["jira:epic:GRT-EPIC"]])
        self.assertEqual(repository.store_calls[0]["ids"], ["jira:epic:GRT-EPIC"])
        self.assertEqual(
            vector_store.upsert_calls[0]["ids"],
            ["jira:issue:cloud-1:GRT:GRT-EPIC"],
        )
        self.assertEqual(
            vector_store.upsert_calls[0]["documents"][0].metadata["entity_type"],
            "issue",
        )
        self.assertIn("jira_issue", vector_store.upsert_calls[0]["documents"][0].metadata)
        self.assertNotIn(
            "jira_epic",
            vector_store.upsert_calls[0]["documents"][0].metadata,
        )
        self.assertEqual(
            vector_store.upsert_calls[0]["documents"][0].metadata["jira_issue"]["type"],
            "Epic",
        )
        self.assertEqual(
            vector_store.upsert_calls[0]["documents"][0].metadata["internal_author_id"],
            "84",
        )
        self.assertEqual(persisted.persisted_count, 1)
        self.assertEqual(persisted.v2_error_count, 0)

    async def test_backfill_builds_v2_document_with_assignee_internal_user_id(self) -> None:
        seed = JiraIssueV2BackfillSeed(
            langchain_id="jira:issue:cloud-1:GRT:GRT-2",
            record_id="GRT-2",
            content="seeded v1 content",
            embedding=[0.1, 0.2, 0.3],
        )
        repository = _FakeRepository()
        vector_store = _FakeVectorStore()
        v2_knowledge_repository = _FakeV2KnowledgeRepository()
        assignee_resolver = _FakeJiraAssigneeResolver()
        adapter = JiraIssueV2BackfillAdapter(
            dependencies=_dependencies(
                _FakeClient(),
                repository,
                vector_store=vector_store,
                v2_knowledge_repository=v2_knowledge_repository,
                assignee_resolver=assignee_resolver,
            ),
        )
        execution = JiraIssueV2BackfillExecutionRequest(
            tenant_id="cloud-1",
            project_key="GRT",
            seeds=(seed,),
        )

        fetched = SimpleNamespace(
            issues=(
                {
                    "key": "GRT-2",
                    "id": "10003",
                    "assignee_account_id": "acc-backfill",
                },
            ),
            failed_record_ids=(),
        )
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

        self.assertEqual(summary.document_ids, (seed.langchain_id,))
        document = vector_store.upsert_calls[0]["documents"][0]
        self.assertEqual(document.id, seed.langchain_id)
        self.assertEqual(document.page_content, seed.content)
        self.assertEqual(document.metadata["internal_author_id"], "126")
        self.assertEqual(
            document.metadata["jira_issue"]["assignee"]["internal_user_id"],
            "126",
        )
        self.assertEqual(assignee_resolver.account_ids, ["acc-backfill"])
        self.assertEqual(vector_store.upsert_calls[0]["ids"], [seed.langchain_id])
        self.assertEqual(vector_store.upsert_calls[0]["embeddings"], [seed.embedding])
        self.assertEqual(
            v2_knowledge_repository.metadata_namespace_checks,
            [{"ids": [seed.langchain_id], "namespace": "jira_issue"}],
        )
        self.assertEqual(persisted.persisted_count, 1)
        self.assertEqual(persisted.v2_error_count, 0)

    async def test_backfill_treats_missing_jira_metadata_as_failed(self) -> None:
        seed = JiraIssueV2BackfillSeed(
            langchain_id="jira:issue:cloud-1:GRT:GRT-2",
            record_id="GRT-2",
            content="seeded v1 content",
            embedding=[0.1, 0.2, 0.3],
        )
        vector_store = _FakeVectorStore()
        v2_knowledge_repository = _FakeV2KnowledgeRepository(
            missing_metadata_ids=(seed.langchain_id,)
        )
        adapter = JiraIssueV2BackfillAdapter(
            dependencies=_dependencies(
                _FakeClient(),
                _FakeRepository(),
                vector_store=vector_store,
                v2_knowledge_repository=v2_knowledge_repository,
            ),
        )
        execution = JiraIssueV2BackfillExecutionRequest(
            tenant_id="cloud-1",
            project_key="GRT",
            seeds=(seed,),
        )
        fetched = SimpleNamespace(
            issues=(
                {
                    "key": "GRT-2",
                    "id": "10003",
                    "assignee_account_id": "acc-backfill",
                },
            ),
            failed_record_ids=(),
        )
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
        self.assertEqual(persisted.persisted_ids, ())
        self.assertEqual(persisted.v2_error_count, 1)
        self.assertEqual(persisted.v2_failed_ids, (seed.langchain_id,))

    async def test_incremental_delete_deletes_v2_document_when_configured(self) -> None:
        client = _FakeClient()
        repository = _FakeRepository()
        vector_store = _FakeVectorStore()
        adapter = JiraIssueIncrementalAdapter(
            dependencies=_dependencies(
                client,
                repository,
                vector_store=vector_store,
            ),
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

        self.assertEqual(
            repository.delete_calls,
            [["jira:issue:GRT-1", "jira:epic:GRT-1"]],
        )
        self.assertEqual(
            vector_store.delete_calls,
            [[
                "jira:issue:cloud-1:GRT:GRT-1",
                "jira:epic:cloud-1:GRT:GRT-1",
            ]],
        )
        self.assertEqual(persisted.deleted_count, 1)
        self.assertEqual(persisted.v2_error_count, 0)
