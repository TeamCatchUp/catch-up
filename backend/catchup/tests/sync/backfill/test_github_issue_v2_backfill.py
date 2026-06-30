from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.connectors.github.queries import build_issues_by_numbers_query
from catchup.connectors.github.schemas import GithubIssue
from catchup.connectors.github.schemas import GithubUser
from catchup.sync.backfill.base import BackfillSeed
from catchup.sync.backfill.base import embedding_to_list
from catchup.sync.backfill.github_issue_v2 import build_github_issue_v1_target_query
from catchup.sync.backfill.github_issue_v2 import (
    build_github_issue_v1_target_seed_query,
)
from catchup.sync.backfill.github_issue_v2 import build_upsert_seed_rows_statement
from catchup.sync.ingestion.adapters.github import GithubIssueV2BackfillAdapter
from catchup.sync.ingestion.adapters.github import GithubIssueV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.github import GithubIssueV2BackfillSeed
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubIssueDocumentBundle,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow


def _seed() -> BackfillSeed:
    return BackfillSeed(
        langchain_id="github:issue:TeamCatchUp/CatchUp:812",
        record_id="812",
        content="summarized v1 issue content",
        embedding=[0.0123, -0.0456, 0.0789],
    )


def _window() -> SyncWindow:
    now = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _make_issue() -> GithubIssue:
    return GithubIssue(
        number=812,
        html_url="https://github.com/TeamCatchUp/CatchUp/issues/812",
        title="Migrate GitHub issue records to v2",
        body="Issue body from GitHub API",
        state="open",
        author=GithubUser(id=1, login="ba2slk", name="TeamMemberC"),
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 11, 0, tzinfo=timezone.utc),
        comments_count=0,
    )


def test_issues_by_numbers_query_uses_aliases_for_one_graphql_request() -> None:
    query = build_issues_by_numbers_query([812, 813])

    assert "query($owner: String!, $repo: String!)" in query
    assert "issue_812: issue(number: 812)" in query
    assert "issue_813: issue(number: 813)" in query
    assert "labels(first: 20)" in query
    assert "milestone" in query
    assert "comments(first: 50)" in query
    assert "totalCount" in query


@pytest.mark.asyncio
async def test_backfill_adapter_fetch_uses_batch_issue_graphql() -> None:
    client = SimpleNamespace(
        get_issues_graphql=AsyncMock(
            return_value={
                "812": {"number": 812},
                "813": {"number": 813},
            }
        )
    )
    adapter = GithubIssueV2BackfillAdapter(
        installation_id=118342815,
        client=client,
        repository=SimpleNamespace(),
        vector_store=SimpleNamespace(),
    )

    fetched = await adapter.fetch(
        execution=GithubIssueV2BackfillExecutionRequest(
            tenant_id="118342815",
            owner="TeamCatchUp",
            repo="CatchUp",
            seeds=(
                GithubIssueV2BackfillSeed(
                    langchain_id="github:issue:TeamCatchUp/CatchUp:812",
                    record_id="812",
                    content="seed 812",
                    embedding=[0.1],
                ),
                GithubIssueV2BackfillSeed(
                    langchain_id="github:issue:TeamCatchUp/CatchUp:813",
                    record_id="813",
                    content="seed 813",
                    embedding=[0.2],
                ),
            ),
        ),
        sync_window=_window(),
    )

    client.get_issues_graphql.assert_awaited_once_with(
        "TeamCatchUp",
        "CatchUp",
        [812, 813],
    )
    assert fetched.exact_items == (
        ("812", {"number": 812}),
        ("813", {"number": 813}),
    )
    assert fetched.failed_record_ids == ()


@pytest.mark.asyncio
async def test_backfill_adapter_hydrates_issue_and_reuses_v1_seed_values() -> None:
    seed = _seed()
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
    )
    v2_knowledge_repository = SimpleNamespace(
        find_missing_metadata_namespace_ids=AsyncMock(return_value=()),
    )
    adapter = GithubIssueV2BackfillAdapter(
        installation_id=118342815,
        client=SimpleNamespace(),
        repository=SimpleNamespace(),
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
    )
    api_items = [("812", {"number": 812})]
    api_document = Document(
        id=seed.langchain_id,
        page_content="fresh semantic content from API",
        metadata={
            "entity_type": "issue",
            "synced_at": "2026-06-10T03:00:00+00:00",
        },
    )

    with (
        patch.object(
            adapter,
            "_fetch_issue_nodes",
            AsyncMock(return_value=(api_items, [])),
        ) as fetch_issue_nodes,
        patch.object(
            adapter,
            "_build_issue_document_bundles_sync",
            Mock(
                return_value=(
                    [
                        GithubIssueDocumentBundle(
                            issue=_make_issue(),
                            document=api_document,
                        )
                    ],
                    [],
                )
            ),
        ) as build_issue_bundles,
    ):
        result = await run_sync_ingestion(
            port=adapter,
            execution=GithubIssueV2BackfillExecutionRequest(
                tenant_id="118342815",
                owner="TeamCatchUp",
                repo="CatchUp",
                seeds=(
                    GithubIssueV2BackfillSeed(
                        langchain_id=seed.langchain_id,
                        record_id=seed.record_id,
                        content=seed.content,
                        embedding=seed.embedding,
                    ),
                ),
            ),
            sync_window=_window(),
        )

    fetch_issue_nodes.assert_awaited_once_with(
        owner="TeamCatchUp",
        repo="CatchUp",
        issue_ids=["812"],
    )
    build_issue_bundles.assert_called_once_with("TeamCatchUp", "CatchUp", api_items)
    vector_store.upsert_documents.assert_awaited_once()
    upsert_call = vector_store.upsert_documents.await_args
    document = upsert_call.args[0][0]

    assert result.persisted_count == 1
    assert result.failed_count == 0
    assert result.metadata["failed_ids"] == []
    assert document.id == seed.langchain_id
    assert document.page_content == "summarized v1 issue content"
    assert document.metadata["title"] == "Migrate GitHub issue records to v2"
    assert document.metadata["body"] == "Issue body from GitHub API"
    assert document.metadata["scope_id"] == "118342815"
    assert document.metadata["github_issue"]["state"] == "open"
    assert document.metadata["data"]["parts"] == [
        {
            "type": "issue_body",
            "text": "Issue body from GitHub API",
            "metadata": {},
        }
    ]
    assert upsert_call.kwargs["ids"] == [seed.langchain_id]
    assert upsert_call.kwargs["embeddings"] == [seed.embedding]
    v2_knowledge_repository.find_missing_metadata_namespace_ids.assert_awaited_once_with(
        [seed.langchain_id],
        namespace="github_issue",
    )


@pytest.mark.asyncio
async def test_backfill_adapter_treats_missing_issue_metadata_as_failed() -> None:
    seed = _seed()
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
    )
    v2_knowledge_repository = SimpleNamespace(
        find_missing_metadata_namespace_ids=AsyncMock(
            return_value=(seed.langchain_id,)
        ),
    )
    adapter = GithubIssueV2BackfillAdapter(
        installation_id=118342815,
        client=SimpleNamespace(),
        repository=SimpleNamespace(),
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
    )
    api_items = [("812", {"number": 812})]
    api_document = Document(
        id=seed.langchain_id,
        page_content="fresh semantic content from API",
        metadata={
            "entity_type": "issue",
            "synced_at": "2026-06-10T03:00:00+00:00",
        },
    )

    with (
        patch.object(
            adapter,
            "_fetch_issue_nodes",
            AsyncMock(return_value=(api_items, [])),
        ),
        patch.object(
            adapter,
            "_build_issue_document_bundles_sync",
            Mock(
                return_value=(
                    [
                        GithubIssueDocumentBundle(
                            issue=_make_issue(),
                            document=api_document,
                        )
                    ],
                    [],
                )
            ),
        ),
    ):
        result = await run_sync_ingestion(
            port=adapter,
            execution=GithubIssueV2BackfillExecutionRequest(
                tenant_id="118342815",
                owner="TeamCatchUp",
                repo="CatchUp",
                seeds=(
                    GithubIssueV2BackfillSeed(
                        langchain_id=seed.langchain_id,
                        record_id=seed.record_id,
                        content=seed.content,
                        embedding=seed.embedding,
                    ),
                ),
            ),
            sync_window=_window(),
        )

    assert result.persisted_count == 0
    assert result.failed_count == 1
    assert result.v2_failed_count == 1
    assert result.metadata["failed_ids"] == [seed.langchain_id]
    assert result.metadata["v2_failed_ids"] == [seed.langchain_id]


@pytest.mark.asyncio
async def test_backfill_adapter_mapper_failure_reports_v2_failed_id() -> None:
    seed = _seed()
    adapter = GithubIssueV2BackfillAdapter(
        installation_id=118342815,
        client=SimpleNamespace(),
        repository=SimpleNamespace(),
        vector_store=SimpleNamespace(upsert_documents=AsyncMock()),
    )
    api_items = [("812", {"number": 812})]
    api_document = Document(
        id=seed.langchain_id,
        page_content="fresh semantic content from API",
        metadata={
            "entity_type": "issue",
            "synced_at": "2026-06-10T03:00:00+00:00",
        },
    )
    adapter.issue_v2_mapper.to_document = Mock(side_effect=ValueError("bad issue"))

    with (
        patch.object(
            adapter,
            "_fetch_issue_nodes",
            AsyncMock(return_value=(api_items, [])),
        ),
        patch.object(
            adapter,
            "_build_issue_document_bundles_sync",
            Mock(
                return_value=(
                    [
                        GithubIssueDocumentBundle(
                            issue=_make_issue(),
                            document=api_document,
                        )
                    ],
                    [],
                )
            ),
        ),
    ):
        result = await run_sync_ingestion(
            port=adapter,
            execution=GithubIssueV2BackfillExecutionRequest(
                tenant_id="118342815",
                owner="TeamCatchUp",
                repo="CatchUp",
                seeds=(
                    GithubIssueV2BackfillSeed(
                        langchain_id=seed.langchain_id,
                        record_id=seed.record_id,
                        content=seed.content,
                        embedding=seed.embedding,
                    ),
                ),
            ),
            sync_window=_window(),
        )

    assert result.persisted_count == 0
    assert result.failed_count == 1
    assert result.v2_failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]
    assert result.metadata["v2_failed_ids"] == [seed.langchain_id]
    adapter.vector_store.upsert_documents.assert_not_awaited()


def test_target_query_groups_v1_issues_by_scope_and_target() -> None:
    query = str(build_github_issue_v1_target_query())

    assert "WITH v1_issue AS" in query
    assert "LEFT JOIN knowledge_store v2" in query
    assert "v2.document_id = v1_issue.langchain_id" in query
    assert "COALESCE(v2.metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in query
    assert "AND e.embedding IS NOT NULL" in query
    assert "count(*) AS expected_count" in query
    assert "count(*) FILTER (WHERE needs_backfill) AS pending_count" in query
    assert "state.connector = 'github'" in query
    assert "state.entity_type = 'issue'" in query
    assert "state.state IN ('pending', 'succeeded')" in query
    assert "state.state = 'failed'" in query
    assert "state.next_retry_at IS NULL" in query
    assert "state.next_retry_at <= now()" in query
    assert "state.state = 'processing'" in query
    assert "state.processing_started_at" in query
    assert "GROUP BY scope_id, target_id" in query


def test_target_seed_query_returns_issue_rows_for_one_target() -> None:
    query = str(build_github_issue_v1_target_seed_query())

    assert "v1_issue.record_id" in query
    assert "candidates.record_id" in query
    assert "candidates.metadata" not in query
    assert "COALESCE(v2.metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in query
    assert "AND e.embedding IS NOT NULL" in query
    assert "WHERE candidates.scope_id = :scope_id" in query
    assert "AND candidates.target_id = :target_id" in query
    assert "AND candidates.needs_backfill" in query
    assert "CAST(:after_record_number AS integer) IS NULL" in query
    assert "record_number > CAST(:after_record_number AS integer)" in query
    assert "record_number = CAST(:after_record_number AS integer)" in query
    assert "langchain_id > COALESCE(CAST(:after_langchain_id AS text), '')" in query
    assert "ORDER BY record_number, langchain_id" in query
    assert "LIMIT :limit" in query
    assert "OFFSET" not in query
    assert "v1_issue.source_updated_at" not in query
    assert "v2.updated_at <" not in query
    assert "v2.content IS DISTINCT FROM" not in query


def test_seed_rows_statement_marks_issue_seed_with_empty_json_metadata() -> None:
    statement = str(build_upsert_seed_rows_statement())

    assert "INSERT INTO knowledge_store" in statement
    assert "CAST(:embedding AS vector)" in statement
    assert "'github'" in statement
    assert "'issue'" in statement
    assert "'{}'::jsonb" in statement
    assert "ON CONFLICT (document_id) DO UPDATE SET" in statement
    assert "metadata = '{}'::json" not in statement
    assert "title = ''" not in statement
    assert "body = ''" not in statement
    assert "data = '{}'::jsonb" not in statement
    assert "url = ''" not in statement


def test_github_issue_v2_embedding_to_list_treats_null_as_empty() -> None:
    assert embedding_to_list(None) == []
