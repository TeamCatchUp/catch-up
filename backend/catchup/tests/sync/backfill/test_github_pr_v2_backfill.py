from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.connectors.github.queries import build_pull_requests_by_numbers_query
from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubUser
from catchup.sync.backfill.github_pr_v2 import GithubPrV1Seed
from catchup.sync.backfill.github_pr_v2 import GithubPrV2BackfillService
from catchup.sync.backfill.github_pr_v2 import build_fetch_seeded_seed_chunk_query
from catchup.sync.backfill.github_pr_v2 import build_github_pr_v1_target_query
from catchup.sync.backfill.github_pr_v2 import build_github_pr_v1_target_seed_query
from catchup.sync.backfill.github_pr_v2 import build_mark_processing_statement
from catchup.sync.backfill.github_pr_v2 import build_upsert_seed_rows_statement
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillAdapter
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillSeed
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubPrDocumentBundle,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self._rows


def _seed() -> GithubPrV1Seed:
    return GithubPrV1Seed(
        langchain_id="github:pr:TeamCatchUp/CatchUp:724",
        record_id="724",
        content="summarized v1 content",
        embedding=[0.0123, -0.0456, 0.0789],
    )


def _target_row(expected_count: int = 1) -> dict:
    return {
        "scope_id": "118342815",
        "target_id": "TeamCatchUp/CatchUp",
        "expected_count": expected_count,
    }


def _seed_row(seed: GithubPrV1Seed) -> dict:
    return {
        "langchain_id": seed.langchain_id,
        "record_id": seed.record_id,
        "content": seed.content,
        "embedding": seed.embedding,
    }


def _window() -> SyncWindow:
    now = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _make_pull_request() -> GithubPullRequest:
    return GithubPullRequest(
        number=724,
        url="https://api.github.com/repos/TeamCatchUp/CatchUp/pulls/724",
        html_url="https://github.com/TeamCatchUp/CatchUp/pull/724",
        title="[CAM-37] refactor backend prompt pipeline",
        body="PR body from GitHub API",
        state="closed",
        merged=True,
        base_ref="develop",
        head_ref="feature/pr-v2",
        author=GithubUser(id=1, login="ba2slk", name="TeamMemberC"),
        created_at=datetime(2026, 5, 19, 20, 13, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 19, 20, 19, 53, tzinfo=timezone.utc),
        merged_at=datetime(2026, 5, 19, 20, 13, 11, tzinfo=timezone.utc),
        closed_at=datetime(2026, 5, 19, 20, 13, 11, tzinfo=timezone.utc),
        changed_files=38,
        additions=120,
        deletions=50,
    )


def test_pull_requests_by_numbers_query_uses_aliases_for_one_graphql_request() -> None:
    query = build_pull_requests_by_numbers_query([724, 725])

    assert "query($owner: String!, $repo: String!)" in query
    assert "pr_724: pullRequest(number: 724)" in query
    assert "pr_725: pullRequest(number: 725)" in query
    assert "title" in query
    assert "reviewThreads" in query


@pytest.mark.asyncio
async def test_backfill_adapter_fetch_uses_batch_pull_request_graphql() -> None:
    client = SimpleNamespace(
        get_pull_requests_graphql=AsyncMock(
            return_value={
                "724": {"number": 724},
                "725": {"number": 725},
            }
        )
    )
    adapter = GithubPrV2BackfillAdapter(
        installation_id=118342815,
        client=client,
        repository=SimpleNamespace(),
        pr_v2_vector_store=SimpleNamespace(),
    )

    fetched = await adapter.fetch(
        execution=GithubPrV2BackfillExecutionRequest(
            tenant_id="118342815",
            owner="TeamCatchUp",
            repo="CatchUp",
            seeds=(
                GithubPrV2BackfillSeed(
                    langchain_id="github:pr:TeamCatchUp/CatchUp:724",
                    record_id="724",
                    content="seed 724",
                    embedding=[0.1],
                ),
                GithubPrV2BackfillSeed(
                    langchain_id="github:pr:TeamCatchUp/CatchUp:725",
                    record_id="725",
                    content="seed 725",
                    embedding=[0.2],
                ),
            ),
        ),
        sync_window=_window(),
    )

    client.get_pull_requests_graphql.assert_awaited_once_with(
        "TeamCatchUp",
        "CatchUp",
        [724, 725],
    )
    assert fetched.exact_items == (
        ("724", {"number": 724}),
        ("725", {"number": 725}),
    )
    assert fetched.failed_record_ids == ()


@pytest.mark.asyncio
async def test_backfill_adapter_fetch_splits_pull_request_graphql_batches_at_50() -> None:
    client = SimpleNamespace(
        get_pull_requests_graphql=AsyncMock(
            side_effect=[
                {str(number): {"number": number} for number in range(1, 51)},
                {"51": {"number": 51}},
            ]
        )
    )
    adapter = GithubPrV2BackfillAdapter(
        installation_id=118342815,
        client=client,
        repository=SimpleNamespace(),
        pr_v2_vector_store=SimpleNamespace(),
    )

    fetched = await adapter.fetch(
        execution=GithubPrV2BackfillExecutionRequest(
            tenant_id="118342815",
            owner="TeamCatchUp",
            repo="CatchUp",
            seeds=tuple(
                GithubPrV2BackfillSeed(
                    langchain_id=f"github:pr:TeamCatchUp/CatchUp:{number}",
                    record_id=str(number),
                    content=f"seed {number}",
                    embedding=[0.1],
                )
                for number in range(1, 52)
            ),
        ),
        sync_window=_window(),
    )

    assert client.get_pull_requests_graphql.await_count == 2
    assert client.get_pull_requests_graphql.await_args_list[0].args == (
        "TeamCatchUp",
        "CatchUp",
        list(range(1, 51)),
    )
    assert client.get_pull_requests_graphql.await_args_list[1].args == (
        "TeamCatchUp",
        "CatchUp",
        [51],
    )
    assert len(fetched.exact_items) == 51
    assert fetched.failed_record_ids == ()


@pytest.mark.asyncio
async def test_backfill_adapter_hydrates_pr_from_api_and_reuses_v1_seed_values() -> None:
    seed = _seed()
    v2_vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id])
    )
    adapter = GithubPrV2BackfillAdapter(
        installation_id=118342815,
        client=SimpleNamespace(),
        repository=SimpleNamespace(),
        pr_v2_vector_store=v2_vector_store,
    )
    api_items = [("724", {"number": 724})]
    api_document = Document(
        id=seed.langchain_id,
        page_content="fresh semantic content from API",
        metadata={
            "entity_type": "pr",
            "synced_at": "2026-06-10T03:00:00+00:00",
        },
    )

    with (
        patch.object(
            adapter,
            "_fetch_pull_request_nodes",
            AsyncMock(return_value=(api_items, [])),
        ) as fetch_pull_request_nodes,
        patch.object(
            adapter,
            "_build_pull_request_document_bundles_sync",
            Mock(
                return_value=(
                    [
                        GithubPrDocumentBundle(
                            pull_request=_make_pull_request(),
                            document=api_document,
                        )
                    ],
                    [],
                )
            ),
        ) as build_pull_request_bundles,
    ):
        result = await run_sync_ingestion(
            port=adapter,
            execution=GithubPrV2BackfillExecutionRequest(
                tenant_id="118342815",
                owner="TeamCatchUp",
                repo="CatchUp",
                seeds=(
                    GithubPrV2BackfillSeed(
                        langchain_id=seed.langchain_id,
                        record_id=seed.record_id,
                        content=seed.content,
                        embedding=seed.embedding,
                    ),
                ),
            ),
            sync_window=_window(),
        )

    fetch_pull_request_nodes.assert_awaited_once_with(
        owner="TeamCatchUp",
        repo="CatchUp",
        pull_request_ids=["724"],
    )
    build_pull_request_bundles.assert_called_once_with(
        "TeamCatchUp",
        "CatchUp",
        api_items,
    )
    v2_vector_store.upsert_documents.assert_awaited_once()
    upsert_call = v2_vector_store.upsert_documents.await_args
    document = upsert_call.args[0][0]

    assert result.persisted_count == 1
    assert result.failed_count == 0
    assert result.metadata["failed_ids"] == []
    assert document.id == seed.langchain_id
    assert document.page_content == "summarized v1 content"
    assert document.metadata["title"] == "[CAM-37] refactor backend prompt pipeline"
    assert document.metadata["body"] == "PR body from GitHub API"
    assert document.metadata["scope_id"] == "118342815"
    assert document.metadata["github_pr"]["additions"] == 120
    assert document.metadata["data"]["parts"] == [
        {"type": "pr_body", "text": "PR body from GitHub API", "metadata": {}}
    ]
    assert upsert_call.kwargs["ids"] == [seed.langchain_id]
    assert upsert_call.kwargs["embeddings"] == [seed.embedding]


def test_target_query_groups_v1_prs_by_scope_and_target() -> None:
    query = str(build_github_pr_v1_target_query())

    assert "LEFT JOIN knowledge_store v2" in query
    assert "v2.document_id = v1_pr.langchain_id" in query
    assert "COALESCE(v2.metadata, '{}'::jsonb) = '{}'::jsonb" in query
    assert "count(*) AS expected_count" in query
    assert "count(*) FILTER (WHERE needs_backfill) AS pending_count" in query
    assert "state.connector = 'github'" in query
    assert "state.entity_type = 'pr'" in query
    assert "state.state != 'processing'" in query
    assert "GROUP BY scope_id, target_id" in query


def test_target_seed_query_returns_backfill_needed_rows_for_one_target() -> None:
    query = str(build_github_pr_v1_target_seed_query())

    assert "v1_pr.record_id" in query
    assert "candidates.record_id" in query
    assert "candidates.metadata" not in query
    assert "COALESCE(v2.metadata, '{}'::jsonb) = '{}'::jsonb" in query
    assert "WHERE candidates.scope_id = :scope_id" in query
    assert "AND candidates.target_id = :target_id" in query
    assert "AND candidates.needs_backfill" in query
    assert "v2.updated_at < v1_pr.source_updated_at" in query
    assert "v2.content IS DISTINCT FROM v1_pr.content" in query


def test_seed_rows_statement_marks_seed_with_empty_json_metadata() -> None:
    statement = str(build_upsert_seed_rows_statement())

    assert "INSERT INTO knowledge_store" in statement
    assert "CAST(:embedding AS vector)" in statement
    assert "'{}'::jsonb" in statement
    assert "ON CONFLICT (document_id) DO UPDATE SET" in statement
    assert "metadata = '{}'::jsonb" in statement


def test_fetch_seeded_seed_chunk_query_reads_v2_seed_rows_by_empty_metadata() -> None:
    query = str(build_fetch_seeded_seed_chunk_query())

    assert "FROM knowledge_store" in query
    assert "source = 'github'" in query
    assert "entity_type = 'pr'" in query
    assert "scope_id = :scope_id" in query
    assert "target_id = :target_id" in query
    assert "COALESCE(metadata, '{}'::jsonb) = '{}'::jsonb" in query
    assert "document_id > :after_langchain_id" in query
    assert "LIMIT :limit" in query


def test_mark_processing_statement_claims_scope_target_conditionally() -> None:
    statement = str(build_mark_processing_statement())

    assert "ON CONFLICT (connector, entity_type, scope_id, target_id)" in statement
    assert "state = 'processing'" in statement
    assert "expected_count = EXCLUDED.expected_count" in statement
    assert "failed_ids = '[]'::jsonb" in statement
    assert "WHERE vector_store_v2_backfill_states.state != 'processing'" in statement
    assert "RETURNING id" in statement


@pytest.mark.asyncio
async def test_backfill_batch_records_scope_success_when_target_seeds_are_persisted() -> None:
    seed = _seed()
    claim_result = MagicMock()
    claim_result.first.return_value = (1,)
    session = MagicMock()
    session.execute.side_effect = [
        _RowsResult([_target_row(expected_count=1)]),
        claim_result,
        _RowsResult([_seed_row(seed)]),
        MagicMock(),
        _RowsResult([_seed_row(seed)]),
        _RowsResult([]),
        MagicMock(),
    ]
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    adapter = SimpleNamespace()
    adapter_factory = AsyncMock(return_value=adapter)
    pipeline_result = SimpleNamespace(
        persisted_count=1,
        failed_count=0,
        metadata={"failed_ids": []},
    )
    service = GithubPrV2BackfillService(
        adapter_factory=adapter_factory,
        session_factory=session_factory,
        collection_name="vectorstore",
    )

    with (
        patch("catchup.sync.backfill.github_pr_v2.logger") as logger_mock,
        patch(
            "catchup.sync.backfill.github_pr_v2.run_sync_ingestion",
            AsyncMock(return_value=pipeline_result),
        ) as run_pipeline,
    ):
        result = await service.backfill_batch(limit=10, locked_by="test-runner")

    assert result.scanned == 1
    assert result.succeeded == 1
    assert result.skipped == 0
    assert result.failed == 0
    adapter_factory.assert_awaited_once_with(118342815)
    run_pipeline.assert_awaited_once()
    pipeline_kwargs = run_pipeline.await_args.kwargs
    assert pipeline_kwargs["port"] is adapter
    assert pipeline_kwargs["execution"].owner == "TeamCatchUp"
    assert pipeline_kwargs["execution"].repo == "CatchUp"
    assert pipeline_kwargs["execution"].seeds[0].langchain_id == seed.langchain_id
    assert pipeline_kwargs["execution"].seeds[0].content == seed.content
    assert pipeline_kwargs["execution"].seeds[0].embedding == seed.embedding
    assert pipeline_kwargs["execution"].seeds[0].record_id == seed.record_id

    seed_insert_params = session.execute.call_args_list[3].args[1]
    assert seed_insert_params[0]["langchain_id"] == seed.langchain_id
    assert seed_insert_params[0]["embedding"] == "[0.0123,-0.0456,0.0789]"
    first_chunk_params = session.execute.call_args_list[4].args[1]
    assert first_chunk_params["limit"] == 50
    assert first_chunk_params["after_langchain_id"] is None
    second_chunk_params = session.execute.call_args_list[5].args[1]
    assert second_chunk_params["limit"] == 50
    assert second_chunk_params["after_langchain_id"] == seed.langchain_id

    finish_params = session.execute.call_args_list[-1].args[1]
    assert finish_params["state"] == "succeeded"
    assert finish_params["expected_count"] == 1
    assert finish_params["backfill_count"] == 1
    assert finish_params["failed_ids"] == []
    assert finish_params["succeeded_at"] is not None
    assert finish_params["failed_at"] is None

    info_events = [call.args[0] for call in logger_mock.info.call_args_list]
    assert info_events == [
        "github_pr_v2_backfill_candidate_targets_fetched",
        "github_pr_v2_backfill_target_claimed",
        "github_pr_v2_backfill_v1_seeds_fetched",
        "github_pr_v2_backfill_seed_rows_upserted",
        "github_pr_v2_backfill_seeded_chunk_started",
        "github_pr_v2_backfill_seeded_chunk_completed",
        "github_pr_v2_backfill_target_finished",
    ]
    candidate_log = logger_mock.info.call_args_list[0]
    assert candidate_log.kwargs["limit"] == 10
    assert candidate_log.kwargs["target_count"] == 1
    seed_log = logger_mock.info.call_args_list[2]
    assert seed_log.kwargs["scope_id"] == "118342815"
    assert seed_log.kwargs["target_id"] == "TeamCatchUp/CatchUp"
    assert seed_log.kwargs["expected_count"] == 1
    assert seed_log.kwargs["seed_count"] == 1
    upsert_log = logger_mock.info.call_args_list[3]
    assert upsert_log.kwargs["upserted_count"] == 1
    assert upsert_log.kwargs["seed_insert_batch_size"] == 100
    chunk_started_log = logger_mock.info.call_args_list[4]
    assert chunk_started_log.kwargs["chunk_index"] == 1
    assert chunk_started_log.kwargs["seed_count"] == 1
    assert chunk_started_log.kwargs["hydrate_batch_size"] == 50
    assert chunk_started_log.kwargs["after_langchain_id"] is None
    assert chunk_started_log.kwargs["last_langchain_id"] == seed.langchain_id
    chunk_completed_log = logger_mock.info.call_args_list[5]
    assert chunk_completed_log.kwargs["persisted_count"] == 1
    assert chunk_completed_log.kwargs["failed_count"] == 0
    assert chunk_completed_log.kwargs["failed_ids"] == []
    target_finished_log = logger_mock.info.call_args_list[6]
    assert target_finished_log.kwargs["state"] == "succeeded"
    assert target_finished_log.kwargs["backfill_count"] == 1
    assert target_finished_log.kwargs["failed_count"] == 0
    assert target_finished_log.kwargs["failed_ids"] == []


@pytest.mark.asyncio
async def test_backfill_batch_skips_when_scope_target_claim_is_not_acquired() -> None:
    claim_result = MagicMock()
    claim_result.first.return_value = None
    session = MagicMock()
    session.execute.side_effect = [
        _RowsResult([_target_row(expected_count=1)]),
        claim_result,
    ]
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    adapter_factory = AsyncMock()
    service = GithubPrV2BackfillService(
        adapter_factory=adapter_factory,
        session_factory=session_factory,
        collection_name="vectorstore",
    )

    with patch("catchup.sync.backfill.github_pr_v2.logger") as logger_mock:
        result = await service.backfill_batch(limit=10, locked_by="test-runner")

    assert result.scanned == 1
    assert result.succeeded == 0
    assert result.skipped == 1
    assert result.failed == 0
    adapter_factory.assert_not_awaited()
    info_events = [call.args[0] for call in logger_mock.info.call_args_list]
    assert info_events == [
        "github_pr_v2_backfill_candidate_targets_fetched",
        "github_pr_v2_backfill_target_claim_skipped",
    ]
    skip_log = logger_mock.info.call_args_list[1]
    assert skip_log.kwargs["scope_id"] == "118342815"
    assert skip_log.kwargs["target_id"] == "TeamCatchUp/CatchUp"
    assert skip_log.kwargs["expected_count"] == 1
    assert skip_log.kwargs["reason"] == "already_processing"


@pytest.mark.asyncio
async def test_backfill_batch_records_failed_ids_when_pipeline_reports_failure() -> None:
    seed = _seed()
    claim_result = MagicMock()
    claim_result.first.return_value = (1,)
    session = MagicMock()
    session.execute.side_effect = [
        _RowsResult([_target_row(expected_count=1)]),
        claim_result,
        _RowsResult([_seed_row(seed)]),
        MagicMock(),
        _RowsResult([_seed_row(seed)]),
        _RowsResult([]),
        MagicMock(),
    ]
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    adapter_factory = AsyncMock(return_value=SimpleNamespace())
    pipeline_result = SimpleNamespace(
        persisted_count=0,
        failed_count=1,
        metadata={"failed_ids": [seed.langchain_id]},
    )
    service = GithubPrV2BackfillService(
        adapter_factory=adapter_factory,
        session_factory=session_factory,
        collection_name="vectorstore",
    )

    with (
        patch("catchup.sync.backfill.github_pr_v2.logger") as logger_mock,
        patch(
            "catchup.sync.backfill.github_pr_v2.run_sync_ingestion",
            AsyncMock(return_value=pipeline_result),
        ) as run_pipeline,
    ):
        result = await service.backfill_batch(limit=10, locked_by="test-runner")

    assert result.scanned == 1
    assert result.succeeded == 0
    assert result.skipped == 0
    assert result.failed == 1
    run_pipeline.assert_awaited_once()

    fail_params = session.execute.call_args_list[-1].args[1]
    assert fail_params["state"] == "failed"
    assert fail_params["backfill_count"] == 0
    assert fail_params["failed_ids"] == [seed.langchain_id]
    assert fail_params["succeeded_at"] is None
    assert fail_params["failed_at"] is not None
    target_finished_log = logger_mock.info.call_args_list[-1]
    assert target_finished_log.args[0] == "github_pr_v2_backfill_target_finished"
    assert target_finished_log.kwargs["state"] == "failed"
    assert target_finished_log.kwargs["backfill_count"] == 0
    assert target_finished_log.kwargs["failed_count"] == 1
    assert target_finished_log.kwargs["failed_ids"] == [seed.langchain_id]
