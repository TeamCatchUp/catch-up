from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.sync.backfill.jira_issue_v2_validation import (
    build_jira_issue_v2_count_validation_query,
)
from catchup.sync.backfill.jira_issue_v2_validation import (
    build_jira_issue_v2_legacy_epic_shape_query,
)
from catchup.sync.backfill.jira_issue_v2_validation import (
    build_jira_issue_v2_sample_query,
)
from catchup.sync.backfill.jira_issue_v2_validation import (
    validate_jira_issue_v2_sample_row,
)


def _dt():
    return datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)


def test_jira_issue_v2_count_validation_uses_unambiguous_cloud_resolution() -> None:
    sql = str(build_jira_issue_v2_count_validation_query())

    assert "NULLIF(e.cmetadata ->> 'cloud_id', '')" in sql
    assert "NULLIF(e.cmetadata ->> 'scope_id', '')" in sql
    assert "e.cmetadata ->> 'entity_type' IN ('issue', 'epic')" in sql
    assert "substring(e.id from '^jira:[^:]+:(.+)$')" in sql
    assert "substring(v1_issue_source.issue_url from '^https?://([^/]+)')" in sql
    assert "project_match_count = 1" in sql
    assert "canonical_rank = 1" in sql
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) ? 'jira_issue'" in sql
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) - 'jira_issue' = '{}'::jsonb" in sql
    assert "v1_issue.target_id" not in sql
    assert "v1_issue.record_id" not in sql
    assert "v1_issue.v1_langchain_id" not in sql


def test_jira_issue_v2_sample_query_uses_exact_metadata_namespace() -> None:
    sql = str(build_jira_issue_v2_sample_query())

    assert "WHERE source = 'jira'" in sql
    assert "entity_type = 'issue'" in sql
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) ? 'jira_issue'" in sql
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) - 'jira_issue' = '{}'::jsonb" in sql


def test_jira_issue_v2_validation_query_does_not_parse_regex_as_bind_param() -> None:
    params = build_jira_issue_v2_count_validation_query().compile().params

    assert "issue" not in params


def test_validate_jira_issue_v2_sample_row_accepts_hydrated_row() -> None:
    result = validate_jira_issue_v2_sample_row(
        {
            "langchain_id": "jira:issue:cloud-1:CATCH:CATCH-145",
            "content": "summarized content",
            "source": "jira",
            "entity_type": "issue",
            "record_id": "CATCH-145",
            "scope_type": "cloud",
            "scope_id": "cloud-1",
            "target_type": "project",
            "target_id": "CATCH",
            "target_name": "CatchUp",
            "title": "Implement Jira v2",
            "body": "Description\n\nComment",
            "data": {
                "parts": [
                    {
                        "type": "issue_description",
                        "text": "Description",
                        "metadata": {},
                    },
                    {
                        "type": "issue_comment",
                        "text": "Comment",
                        "metadata": {"id": "comment-1"},
                    },
                ]
            },
            "url": "https://catchup.atlassian.net/browse/CATCH-145",
            "created_at": _dt(),
            "updated_at": _dt(),
            "synced_at": _dt(),
            "langchain_metadata": {
                "jira_issue": {
                    "issue_id": "100145",
                    "type": "Task",
                }
            },
        }
    )

    assert result.is_valid
    assert result.errors == ()


def test_validate_jira_issue_v2_sample_row_rejects_raw_metadata_and_parts() -> None:
    result = validate_jira_issue_v2_sample_row(
        {
            "langchain_id": "jira:issue:cloud-1:CATCH:CATCH-145",
            "content": "summarized content",
            "source": "jira",
            "entity_type": "issue",
            "record_id": "CATCH-145",
            "scope_type": "cloud",
            "scope_id": "cloud-1",
            "target_type": "project",
            "target_id": "CATCH",
            "target_name": "CatchUp",
            "title": "Implement Jira v2",
            "body": "",
            "data": {"parts": [{"type": "raw_adf", "text": "", "metadata": {}}]},
            "url": "https://catchup.atlassian.net/browse/CATCH-145",
            "created_at": _dt(),
            "updated_at": _dt(),
            "synced_at": _dt(),
            "langchain_metadata": {
                "jira_issue": {
                    "issue_id": "100145",
                    "issue_type": "Task",
                    "issue_key": "CATCH-145",
                    "project_key": "CATCH",
                    "project_name": "CatchUp",
                    "reporter": {"catchup_user_id": "usr_author"},
                    "custom_fields": {"raw": True},
                    "comments_count": 1,
                    "attachments_count": 1,
                    "linked_issue_count": 1,
                }
            },
        }
    )

    assert "invalid:data.parts[0].type" in result.errors
    assert "missing:data.parts[0].text" in result.errors
    assert "forbidden:jira_issue.issue_key" in result.errors
    assert "forbidden:jira_issue.project_key" in result.errors
    assert "forbidden:jira_issue.project_name" in result.errors
    assert "forbidden:jira_issue.custom_fields" in result.errors
    assert "forbidden:jira_issue.issue_type" in result.errors
    assert "forbidden:jira_issue.comments_count" in result.errors
    assert "forbidden:jira_issue.attachments_count" in result.errors
    assert "forbidden:jira_issue.linked_issue_count" in result.errors


def test_jira_issue_v2_legacy_epic_shape_query_finds_old_v2_rows() -> None:
    sql = str(build_jira_issue_v2_legacy_epic_shape_query())

    assert "entity_type = 'epic'" in sql
    assert "document_id LIKE 'jira:epic:%'" in sql
    assert "? 'jira_epic'" in sql
