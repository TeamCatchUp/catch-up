from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.sync.backfill.github_pr_v2_validation import (
    build_github_pr_v2_count_validation_query,
)
from catchup.sync.backfill.github_pr_v2_validation import (
    build_github_pr_v2_sample_query,
)
from catchup.sync.backfill.github_pr_v2_validation import (
    validate_github_pr_v2_sample_row,
)


def _valid_row() -> dict:
    return {
        "langchain_id": "github:pr:TeamCatchUp/CatchUp:724",
        "content": "summarized content",
        "source": "github",
        "entity_type": "pr",
        "record_id": "724",
        "scope_type": "installation",
        "scope_id": "118342815",
        "target_type": "repository",
        "target_id": "TeamCatchUp/CatchUp",
        "target_name": "TeamCatchUp/CatchUp",
        "title": "[CAM-37] refactor backend prompt pipeline",
        "body": "PR body\n\nduplicated",
        "data": {
            "parts": [
                {"type": "pr_body", "text": "PR body", "metadata": {}},
                {
                    "type": "review_comment",
                    "text": "duplicated",
                    "metadata": {"path": "backend/file.py", "line": 9},
                },
            ]
        },
        "url": "https://github.com/TeamCatchUp/CatchUp/pull/724",
        "created_at": datetime(2026, 5, 19, 20, 13, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 5, 19, 20, 19, 53, tzinfo=timezone.utc),
        "synced_at": datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc),
        "langchain_metadata": {
            "github_pr": {
                "state": "merged",
                "merged_at": "2026-05-19T20:13:11+00:00",
                "closed_at": "2026-05-19T20:13:11+00:00",
                "base_ref": "develop",
                "head_ref": "feature/pr-v2",
                "is_draft": False,
                "review_decision": "COMMENTED",
                "changed_files": 38,
                "additions": 120,
                "deletions": 50,
                "author": {
                    "login": "ba2slk",
                    "name": "팀원C",
                    "email": "ba2slk@example.com",
                    "catchup_user_id": "usr_github_ba2slk",
                },
                "assignees": [],
                "requested_reviewers": [],
                "review_authors": [],
                "merged_by": None,
                "labels": [],
                "milestone": None,
            }
        },
    }


def test_count_validation_query_compares_v1_and_v2_pr_sets() -> None:
    query = str(build_github_pr_v2_count_validation_query())

    assert "WITH v1_pr AS" in query
    assert "knowledge_store" in query
    assert "document_id AS langchain_id" in query
    assert "missing_in_v2" in query
    assert "extra_in_v2" in query
    assert "e.cmetadata ->> 'entity_type' = 'pr'" in query
    assert "COALESCE(metadata, '{}'::jsonb) != '{}'::jsonb" in query


def test_sample_query_returns_required_v2_projection() -> None:
    query = str(build_github_pr_v2_sample_query())

    assert "document_id AS langchain_id" in query
    assert "body" in query
    assert "data" in query
    assert "metadata" in query
    assert "AS langchain_metadata" in query
    assert "WHERE source = 'github'" in query
    assert "entity_type = 'pr'" in query
    assert "COALESCE(metadata, '{}'::jsonb) != '{}'::jsonb" in query


def test_sample_validator_accepts_valid_github_pr_v2_row() -> None:
    result = validate_github_pr_v2_sample_row(_valid_row())

    assert result.langchain_id == "github:pr:TeamCatchUp/CatchUp:724"
    assert result.is_valid is True
    assert result.errors == ()


def test_sample_validator_rejects_contextual_content_and_bad_types() -> None:
    row = _valid_row()
    row["langchain_metadata"] = {
        "contextual_content": "legacy blob",
        "github_pr": {
            "state": "merged",
            "merged": "true",
            "base_ref": "develop",
            "head_ref": "feature/pr-v2",
            "changed_files": "38",
            "commits_count": 24,
            "comments_count": 4,
            "contextual_content": "legacy blob",
        },
    }

    result = validate_github_pr_v2_sample_row(row)

    assert result.is_valid is False
    assert "invalid:metadata_namespace" in result.errors
    assert "forbidden:contextual_content" in result.errors
    assert "forbidden:github_pr.merged" in result.errors
    assert "forbidden:github_pr.commits_count" in result.errors
