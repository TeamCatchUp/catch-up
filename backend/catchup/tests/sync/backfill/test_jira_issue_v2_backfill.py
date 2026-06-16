from __future__ import annotations

from catchup.sync.backfill.jira_issue_v2 import build_fetch_pending_seed_chunk_query
from catchup.sync.backfill.jira_issue_v2 import build_jira_issue_v1_target_query
from catchup.sync.backfill.jira_issue_v2 import build_jira_issue_v1_target_seed_query
from catchup.sync.backfill.jira_issue_v2 import build_upsert_seed_rows_statement


def _sql(statement) -> str:
    return str(statement)


def test_jira_issue_v2_backfill_targets_join_jira_projects_for_cloud_scope() -> None:
    sql = _sql(build_jira_issue_v1_target_query())

    assert "JOIN jira_projects jp" in sql
    assert "jp.cloud_id AS scope_id" in sql
    assert "jp.project_name AS target_name" in sql
    assert "'jira:issue:' || jp.cloud_id" in sql
    assert "NULLIF(e.cmetadata ->> 'cloud_id', '')" in sql
    assert "NULLIF(e.cmetadata ->> 'scope_id', '')" in sql
    assert "substring(v1_issue.issue_url from '^https?://([^/]+)')" in sql
    assert "project_match_count = 1" in sql
    assert "state.connector = 'jira'" in sql


def test_jira_issue_v2_backfill_seed_query_builds_v2_document_ids() -> None:
    sql = _sql(build_jira_issue_v1_target_seed_query())

    assert "SELECT langchain_id, record_id, content, embedding" in sql
    assert "AND target_id = :target_id" in sql
    assert "ORDER BY target_id, record_id, langchain_id" in sql
    assert "'jira:issue:' || jp.cloud_id" in sql
    assert "project_match_count = 1" in sql


def test_jira_issue_v2_seed_rows_preserve_content_embedding_and_empty_metadata() -> None:
    sql = _sql(build_upsert_seed_rows_statement())

    assert ":content" in sql
    assert "CAST(:embedding AS vector)" in sql
    assert "'{}'::json" in sql
    assert "'jira'" in sql
    assert "'cloud'" in sql
    assert "'project'" in sql


def test_jira_issue_v2_seed_chunk_cursor_is_lexicographic() -> None:
    sql = _sql(build_fetch_pending_seed_chunk_query())

    assert "record_id > :after_record_id" in sql
    assert "AND document_id > COALESCE(:after_langchain_id, '')" in sql
    assert "ORDER BY record_id, document_id" in sql
    assert "::integer" not in sql
    assert "::numeric" not in sql
