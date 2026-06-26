from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.sync.backfill.github_issue_v2_validation import (
    build_github_issue_v2_count_validation_query,
)
from catchup.sync.backfill.github_issue_v2_validation import (
    build_github_issue_v2_sample_query,
)
from catchup.sync.backfill.github_issue_v2_validation import (
    validate_github_issue_v2_sample_row,
)


def _valid_row() -> dict:
    return {
        "langchain_id": "github:issue:TeamCatchUp/CatchUp:812",
        "content": "summarized issue content",
        "source": "github",
        "entity_type": "issue",
        "record_id": "812",
        "scope_type": "installation",
        "scope_id": "118342815",
        "target_type": "repository",
        "target_id": "TeamCatchUp/CatchUp",
        "target_name": "TeamCatchUp/CatchUp",
        "title": "Migrate GitHub issue records to v2",
        "body": "",
        "data": {
            "parts": [
                {"type": "issue_body", "text": "Issue body", "metadata": {}},
                {
                    "type": "issue_comment",
                    "text": "Please keep v1 metadata stable.",
                    "metadata": {"id": "IC_kwDOIssueComment"},
                },
            ]
        },
        "url": "https://github.com/TeamCatchUp/CatchUp/issues/812",
        "created_at": datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 6, 1, 11, 0, tzinfo=timezone.utc),
        "synced_at": datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc),
        "langchain_metadata": {
            "github_issue": {
                "state": "open",
                "state_reason": None,
                "closed_at": None,
                "author": {
                    "external_user_id": "ba2slk",
                    "internal_user_id": "usr_github_ba2slk",
                },
                "assignees": [],
                "labels": [],
                "milestone": None,
            }
        },
    }


def test_count_validation_query_compares_v1_and_v2_issue_sets() -> None:
    query = str(build_github_issue_v2_count_validation_query())

    assert "WITH v1_issue AS" in query
    assert "knowledge_store" in query
    assert "document_id AS langchain_id" in query
    assert "missing_in_v2" in query
    assert "extra_in_v2" in query
    assert "e.cmetadata ->> 'entity_type' = 'issue'" in query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) ? 'github_issue'" in query
    assert (
        "COALESCE(metadata::jsonb, '{}'::jsonb) - 'github_issue' = '{}'::jsonb"
        in query
    )


def test_sample_query_returns_required_issue_v2_projection() -> None:
    query = str(build_github_issue_v2_sample_query())

    assert "document_id AS langchain_id" in query
    assert "body" in query
    assert "data" in query
    assert "metadata" in query
    assert "AS langchain_metadata" in query
    assert "WHERE source = 'github'" in query
    assert "entity_type = 'issue'" in query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) ? 'github_issue'" in query
    assert (
        "COALESCE(metadata::jsonb, '{}'::jsonb) - 'github_issue' = '{}'::jsonb"
        in query
    )


def test_sample_validator_accepts_valid_github_issue_v2_row_with_empty_body() -> None:
    result = validate_github_issue_v2_sample_row(_valid_row())

    assert result.langchain_id == "github:issue:TeamCatchUp/CatchUp:812"
    assert result.is_valid is True
    assert result.errors == ()


def test_sample_validator_rejects_pr_fields_and_contextual_content() -> None:
    row = _valid_row()
    row["langchain_metadata"] = {
        "contextual_content": "legacy blob",
        "github_issue": {
            "state": "open",
            "merged": False,
            "commits_count": 1,
            "review_state": "APPROVED",
            "contextual_content": "legacy blob",
        },
    }

    result = validate_github_issue_v2_sample_row(row)

    assert result.is_valid is False
    assert "invalid:metadata_namespace" in result.errors
    assert "forbidden:contextual_content" in result.errors
    assert "forbidden:github_issue.contextual_content" in result.errors
    assert "forbidden:github_issue.merged" in result.errors
    assert "forbidden:github_issue.commits_count" in result.errors
    assert "forbidden:github_issue.review_state" in result.errors
