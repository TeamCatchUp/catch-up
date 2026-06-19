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


@pytest.mark.parametrize(
    "statement_builder",
    [
        build_channel_talk_document_article_mark_finished_statement,
        build_channel_talk_user_chat_mark_finished_statement,
        build_github_issue_mark_finished_statement,
        build_github_pr_mark_finished_statement,
        build_jira_issue_mark_finished_statement,
        build_slack_message_mark_finished_statement,
    ],
)
def test_mark_finished_statement_casts_reused_state_parameter(statement_builder) -> None:
    sql = str(statement_builder())

    assert "state = CAST(:state AS varchar(32))" in sql
    assert "WHEN CAST(:state AS varchar(32)) = 'failed'" in sql
    assert "failed_ids = CAST(:failed_ids AS jsonb)" in sql
    assert "processing_started_at = NULL" in sql
    assert "AND processing_started_at = :processing_started_at" in sql
