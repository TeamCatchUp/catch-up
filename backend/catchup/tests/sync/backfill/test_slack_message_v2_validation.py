from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.sync.backfill.slack_message_v2_validation import (
    build_slack_message_v2_count_validation_query,
)
from catchup.sync.backfill.slack_message_v2_validation import (
    build_slack_message_v2_sample_query,
)
from catchup.sync.backfill.slack_message_v2_validation import (
    validate_slack_message_v2_sample_row,
)


def _valid_row() -> dict:
    return {
        "langchain_id": "slack:message:T123:C123:1712345678.000100",
        "content": "summarized message content",
        "source": "slack",
        "entity_type": "message",
        "record_id": "1712345678.000100",
        "scope_type": "workspace",
        "scope_id": "T123",
        "target_type": "channel",
        "target_id": "C123",
        "target_name": "general",
        "title": "Slack message v2 migration",
        "body": "",
        "data": {
            "parts": [
                {"type": "message_body", "text": "Message body", "metadata": {}},
                {"type": "thread_reply", "text": "Reply body", "metadata": {}},
            ]
        },
        "url": "https://acme.slack.com/archives/C123/p1712345678000100",
        "created_at": datetime(2024, 4, 5, 12, 34, 38, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 4, 5, 12, 35, tzinfo=timezone.utc),
        "synced_at": datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
        "langchain_metadata": {
            "slack_message": {
                "team_id": "T123",
                "channel_id": "C123",
                "channel_name": "general",
                "ts": "1712345678.000100",
                "thread_ts": "1712345678.000100",
                "is_thread_root": True,
                "author": {"slack_user_id": "U123", "catchup_user_id": "42"},
                "reply_count": 1,
                "reactions": [],
                "edited_at": None,
            }
        },
    }


def test_count_validation_query_ignores_empty_seed_metadata_rows() -> None:
    query = str(build_slack_message_v2_count_validation_query())

    assert "WITH v1_message AS" in query
    assert "WHERE source = 'slack'" in query
    assert "entity_type = 'message'" in query
    assert "missing_in_v2" in query
    assert "extra_in_v2" in query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) != '{}'::jsonb" in query


def test_sample_query_returns_hydrated_slack_message_rows_only() -> None:
    query = str(build_slack_message_v2_sample_query())

    assert "document_id AS langchain_id" in query
    assert "AS langchain_metadata" in query
    assert "WHERE source = 'slack'" in query
    assert "entity_type = 'message'" in query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) != '{}'::jsonb" in query


def test_sample_validator_accepts_valid_slack_message_v2_row() -> None:
    result = validate_slack_message_v2_sample_row(_valid_row())

    assert result.langchain_id == "slack:message:T123:C123:1712345678.000100"
    assert result.is_valid is True
    assert result.errors == ()


def test_sample_validator_rejects_legacy_metadata_blobs() -> None:
    row = _valid_row()
    row["langchain_metadata"] = {
        "contextual_content": "legacy blob",
        "slack_message": {
            "team_id": "T123",
            "channel_id": "C123",
            "channel_name": "general",
            "ts": "1712345678.000100",
            "files": [],
            "attachments": [],
            "author_name": "Hxxukii",
            "contextual_content": "legacy blob",
        },
    }

    result = validate_slack_message_v2_sample_row(row)

    assert result.is_valid is False
    assert "invalid:metadata_namespace" in result.errors
    assert "forbidden:contextual_content" in result.errors
    assert "forbidden:slack_message.contextual_content" in result.errors
    assert "forbidden:slack_message.files" in result.errors
    assert "forbidden:slack_message.attachments" in result.errors
    assert "forbidden:slack_message.author_name" in result.errors
