from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import AsyncMock

from langchain_core.documents import Document

from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.adapters.github.repository_base import (
    GithubRepositoryAdapterBase,
)
from catchup.sync.ingestion.adapters.slack.message_base import SlackMessageAdapterBase


def _audit_context(connector: SyncConnector) -> SyncAuditContext:
    return SyncAuditContext(
        connector=connector,
        scope_id="scope-1",
        target_id="target-1",
        job_id="job-1",
        task_id="task-1",
    )


class IngestionAdapterInitializationTests(TestCase):
    def test_github_adapter_stores_installation_id_as_scope_id(self) -> None:
        vector_store = SimpleNamespace()
        adapter = GithubRepositoryAdapterBase(
            installation_id=123,
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            vector_store=vector_store,
        )

        self.assertEqual(adapter.scope_id, 123)
        self.assertIs(adapter.vector_store, vector_store)
        self.assertFalse(hasattr(adapter, "target_id"))
        self.assertFalse(hasattr(adapter, "installation_id"))

    def test_slack_adapter_preserves_team_fields_and_user_cache_identity(self) -> None:
        adapter = SlackMessageAdapterBase(
            team_id="T123",
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            bot_user_id="B123",
        )

        self.assertEqual(adapter.scope_id, "T123")
        self.assertEqual(adapter.team_id, "T123")
        self.assertEqual(adapter.bot_user_id, "B123")
        self.assertIsNone(adapter.vector_store)
        self.assertIs(adapter.transformer.user_cache, adapter.user_cache)
        self.assertIsNone(adapter.workspace_domain)


class IngestionAdapterSummarizationTests(IsolatedAsyncioTestCase):
    async def test_github_summary_uses_shared_base_without_changing_requests(
        self,
    ) -> None:
        summarizer = SimpleNamespace(
            summarize_batch=AsyncMock(return_value=["summary one", "summary two"])
        )
        adapter = GithubRepositoryAdapterBase(
            installation_id=123,
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            summarizer=summarizer,
        )
        audit_context = _audit_context(SyncConnector.GITHUB)
        first = Document(
            page_content="original one",
            metadata={
                "contextual_content": "contextual one",
                "entity_type": "pr",
            },
        )
        second = Document(page_content="original two", metadata={})

        result = await adapter._summarize_documents(
            [first, second],
            repo_full_name="octo-org/octo-repo",
            entity_type="issue",
            audit_context=audit_context,
        )

        self.assertEqual(result, [first, second])
        self.assertEqual(first.page_content, "summary one")
        self.assertEqual(second.page_content, "summary two")
        summarizer.summarize_batch.assert_awaited_once()
        call = summarizer.summarize_batch.await_args
        requests = call.args[0]
        self.assertEqual(
            [(request.content, request.source_type) for request in requests],
            [
                ("contextual one", "github_pr"),
                ("original two", "github_issue"),
            ],
        )
        self.assertIs(call.kwargs["audit_context"], audit_context)
        self.assertEqual(
            call.kwargs["context"],
            "entity_type=issue,repo=octo-org/octo-repo,doc_count=2",
        )

    async def test_slack_summary_uses_shared_base_without_changing_requests(
        self,
    ) -> None:
        summarizer = SimpleNamespace(
            summarize_batch=AsyncMock(return_value=["summary one", "summary two"])
        )
        adapter = SlackMessageAdapterBase(
            team_id="T123",
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            summarizer=summarizer,
        )
        audit_context = _audit_context(SyncConnector.SLACK)
        first = Document(
            page_content="original one",
            metadata={
                "contextual_content": "contextual one",
                "entity_type": "thread",
            },
        )
        second = Document(page_content="original two", metadata={})

        result = await adapter._summarize_documents(
            [first, second],
            channel_name="general",
            audit_context=audit_context,
        )

        self.assertEqual(result, [first, second])
        self.assertEqual(first.page_content, "summary one")
        self.assertEqual(second.page_content, "summary two")
        summarizer.summarize_batch.assert_awaited_once()
        call = summarizer.summarize_batch.await_args
        requests = call.args[0]
        self.assertEqual(
            [(request.content, request.source_type) for request in requests],
            [
                ("contextual one", "slack_thread"),
                ("original two", "slack_message"),
            ],
        )
        self.assertIs(call.kwargs["audit_context"], audit_context)
        self.assertEqual(
            call.kwargs["context"],
            "entity_type=message,channel=general,doc_count=2",
        )
