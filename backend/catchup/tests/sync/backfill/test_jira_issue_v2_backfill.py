from __future__ import annotations

import json
from unittest.mock import MagicMock

from catchup.sync.backfill.jira_issue_v2 import JiraIssueV1Target
from catchup.sync.backfill.jira_issue_v2 import JiraIssueV2BackfillService
from catchup.sync.backfill.jira_issue_v2 import _embedding_to_list
from catchup.sync.backfill.jira_issue_v2 import build_fetch_pending_seed_chunk_query
from catchup.sync.backfill.jira_issue_v2 import build_jira_issue_v1_target_query
from catchup.sync.backfill.jira_issue_v2 import build_jira_issue_v1_target_seed_query
from catchup.sync.backfill.jira_issue_v2 import build_mark_finished_statement
from catchup.sync.backfill.jira_issue_v2 import build_upsert_seed_rows_statement


def _sql(statement) -> str:
    return str(statement)


def test_jira_issue_v2_backfill_targets_join_jira_projects_for_cloud_scope() -> None:
    sql = _sql(build_jira_issue_v1_target_query())

    assert "JOIN jira_projects jp" in sql
    assert "jp.cloud_id AS scope_id" in sql
    assert "jp.project_name AS target_name" in sql
    assert "'jira:issue:' || jp.cloud_id" in sql
    assert "e.cmetadata ->> 'entity_type' IN ('issue', 'epic')" in sql
    assert "substring(e.id from '^jira:(?:issue|epic):(.+)$')" in sql
    assert "NULLIF(e.cmetadata ->> 'cloud_id', '')" in sql
    assert "NULLIF(e.cmetadata ->> 'scope_id', '')" in sql
    assert "substring(v1_issue_source.issue_url from '^https?://([^/]+)')" in sql
    assert "project_match_count = 1" in sql
    assert "canonical_rank = 1" in sql
    assert "state.connector = 'jira'" in sql
    assert "state.entity_type = 'issue'" in sql


def test_jira_issue_v2_backfill_seed_query_builds_v2_document_ids() -> None:
    sql = _sql(build_jira_issue_v1_target_seed_query())

    assert "SELECT langchain_id, record_id, content, embedding" in sql
    assert "AND target_id = :target_id" in sql
    assert "ORDER BY target_id, record_id, langchain_id" in sql
    assert "'jira:issue:' || jp.cloud_id" in sql
    assert "'jira:epic:' || jp.cloud_id" not in sql
    assert "project_match_count = 1" in sql


def test_jira_issue_v2_backfill_reads_epic_sources_into_issue_rows() -> None:
    target_sql = _sql(build_jira_issue_v1_target_query())
    seed_sql = _sql(build_jira_issue_v1_target_seed_query())
    upsert_sql = _sql(build_upsert_seed_rows_statement())
    chunk_sql = _sql(build_fetch_pending_seed_chunk_query())

    assert "e.cmetadata ->> 'entity_type' IN ('issue', 'epic')" in target_sql
    assert "'jira:issue:' || jp.cloud_id" in target_sql
    assert "'jira:epic:' || jp.cloud_id" not in target_sql
    assert "state.entity_type = 'issue'" in target_sql
    assert "e.cmetadata ->> 'entity_type' IN ('issue', 'epic')" in seed_sql
    assert "'jira:issue:' || jp.cloud_id" in seed_sql
    assert "'jira:epic:' || jp.cloud_id" not in seed_sql
    assert "'issue'" in upsert_sql
    assert "AND entity_type = 'issue'" in chunk_sql


def test_jira_issue_v2_seed_rows_preserve_content_embedding_and_empty_metadata() -> None:
    sql = _sql(build_upsert_seed_rows_statement())

    assert ":content" in sql
    assert "CAST(:embedding AS vector)" in sql
    assert "'{}'::json" in sql
    assert "'jira'" in sql
    assert "'cloud'" in sql
    assert "'project'" in sql


def test_jira_issue_v2_mark_finished_casts_failed_ids_to_jsonb() -> None:
    sql = _sql(build_mark_finished_statement())

    assert "failed_ids = CAST(:failed_ids AS jsonb)" in sql


def test_jira_issue_v2_mark_finished_serializes_failed_ids() -> None:
    session = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = session
    service = JiraIssueV2BackfillService(session_factory=lambda: context)

    service._mark_finished_sync(
        JiraIssueV1Target(
            scope_id="cloud-123",
            target_id="CAT",
            target_name="CatchUp",
            expected_count=1,
        ),
        backfill_count=0,
        failed_ids=["jira:issue:cloud-123:CAT:CAT-1"],
        force_failed=True,
    )

    params = session.execute.call_args.args[1]
    assert json.loads(params["failed_ids"]) == ["jira:issue:cloud-123:CAT:CAT-1"]
    assert isinstance(params["failed_ids"], str)


def test_jira_issue_v2_mark_finished_always_uses_issue_state_key() -> None:
    session = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = session
    service = JiraIssueV2BackfillService(session_factory=lambda: context)

    service._mark_finished_sync(
        JiraIssueV1Target(
            scope_id="cloud-123",
            target_id="CAT",
            target_name="CatchUp",
            expected_count=1,
        ),
        backfill_count=1,
        failed_ids=[],
    )

    params = session.execute.call_args.args[1]
    assert params["entity_type"] == "issue"
    assert json.loads(params["failed_ids"]) == []


def test_jira_issue_v2_embedding_to_list_treats_null_as_empty() -> None:
    assert _embedding_to_list(None) == []


def test_jira_issue_v2_seed_chunk_cursor_is_lexicographic() -> None:
    sql = _sql(build_fetch_pending_seed_chunk_query())

    assert "CAST(:after_record_id AS text) IS NULL" in sql
    assert "record_id > CAST(:after_record_id AS text)" in sql
    assert "record_id = CAST(:after_record_id AS text)" in sql
    assert "AND document_id > COALESCE(CAST(:after_langchain_id AS text), '')" in sql
    assert "ORDER BY record_id, document_id" in sql
    assert "::integer" not in sql
    assert "::numeric" not in sql
