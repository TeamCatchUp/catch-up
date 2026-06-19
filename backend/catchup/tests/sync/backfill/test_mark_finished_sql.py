from __future__ import annotations

import pytest

from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_channel_talk_document_article_mark_finished_statement,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_mark_finished_statement as build_channel_talk_user_chat_mark_finished_statement,
)
from catchup.sync.backfill.github_issue_v2 import (
    build_mark_finished_statement as build_github_issue_mark_finished_statement,
)
from catchup.sync.backfill.github_pr_v2 import (
    build_mark_finished_statement as build_github_pr_mark_finished_statement,
)
from catchup.sync.backfill.jira_issue_v2 import (
    build_mark_finished_statement as build_jira_issue_mark_finished_statement,
)
from catchup.sync.backfill.slack_message_v2 import (
    build_mark_finished_statement as build_slack_message_mark_finished_statement,
)
from catchup.sync.backfill.state import (
    build_mark_finished_statement as build_shared_mark_finished_statement,
)
from catchup.sync.backfill.state import (
    build_mark_processing_statement as build_shared_mark_processing_statement,
)


@pytest.mark.parametrize(
    "statement_builder",
    [
        build_channel_talk_document_article_mark_finished_statement,
        build_channel_talk_user_chat_mark_finished_statement,
        build_github_issue_mark_finished_statement,
        build_github_pr_mark_finished_statement,
        build_jira_issue_mark_finished_statement,
        build_slack_message_mark_finished_statement,
        build_shared_mark_finished_statement,
    ],
)
def test_mark_finished_statement_casts_reused_state_parameter(statement_builder) -> None:
    sql = str(statement_builder())

    assert "state = CAST(:state AS varchar(32))" in sql
    assert "WHEN CAST(:state AS varchar(32)) = 'failed'" in sql
    assert "failed_ids = CAST(:failed_ids AS jsonb)" in sql
    assert "processing_started_at = NULL" in sql
    assert "AND processing_started_at = :processing_started_at" in sql


def test_mark_processing_statement_claims_scope_target_conditionally() -> None:
    statement = str(build_shared_mark_processing_statement())

    assert "ON CONFLICT (connector, entity_type, scope_id, target_id)" in statement
    assert "state = 'processing'" in statement
    assert "expected_count = EXCLUDED.expected_count" in statement
    assert "failed_ids = '[]'::jsonb" in statement
    assert "processing_started_at = now()" in statement
    assert "failure_count = 0" not in statement.split(
        "ON CONFLICT (connector, entity_type, scope_id, target_id) DO UPDATE SET"
    )[1]
    assert "vector_store_v2_backfill_states.state IN ('pending', 'succeeded')" in statement
    assert "vector_store_v2_backfill_states.next_retry_at IS NULL" in statement
    assert "vector_store_v2_backfill_states.next_retry_at <= now()" in statement
    assert "vector_store_v2_backfill_states.processing_started_at IS NULL" in statement
    assert "RETURNING processing_started_at" in statement
