from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.sync.backfill import ChannelTalkArticleV2ValidationService
from catchup.sync.backfill import ChannelTalkUserChatV2ValidationService
from catchup.sync.backfill import JiraIssueV2ValidationService
from catchup.sync.backfill.channel_talk_v2_validation import (
    build_channel_talk_document_article_v2_count_validation_query,
)
from catchup.sync.backfill.channel_talk_v2_validation import (
    build_channel_talk_document_article_v2_sample_query,
)
from catchup.sync.backfill.channel_talk_v2_validation import (
    build_channel_talk_user_chat_v2_count_validation_query,
)
from catchup.sync.backfill.channel_talk_v2_validation import (
    build_channel_talk_user_chat_v2_sample_query,
)
from catchup.sync.backfill.channel_talk_v2_validation import (
    validate_channel_talk_document_article_v2_sample_row,
)
from catchup.sync.backfill.channel_talk_v2_validation import (
    validate_channel_talk_user_chat_v2_sample_row,
)


def _dt() -> datetime:
    return datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc)


def _valid_user_chat_row() -> dict:
    return {
        "langchain_id": "channel_talk:user_chat:channel-1:chat-1",
        "content": "summarized user chat",
        "source": "channel_talk",
        "entity_type": "user_chat",
        "record_id": "chat-1",
        "scope_type": "channel",
        "scope_id": "channel-1",
        "target_type": "channel",
        "target_id": "channel-1",
        "target_name": "CatchUp",
        "title": "User chat",
        "body": "Hello",
        "data": {
            "parts": [
                {
                    "type": "message",
                    "text": "Hello",
                    "metadata": {"message_id": "message-1"},
                }
            ]
        },
        "url": "https://desk.channel.io/#/channels/channel-1/user_chats/chat-1",
        "created_at": _dt(),
        "updated_at": _dt(),
        "synced_at": _dt(),
        "langchain_metadata": {
            "channel_talk_user_chat": {
                "state": "opened",
                "managed": True,
                "priority": None,
                "goal_state": None,
                "customer": None,
                "assignment": {"manager_ids": []},
                "messages": {
                    "count": 1,
                    "included_part_count": 1,
                    "excluded_message_count": 0,
                    "author_types": ["manager"],
                },
                "timing": {},
                "metrics": {},
                "anchors": {},
                "tags": [],
            }
        },
    }


def _valid_document_article_row() -> dict:
    return {
        "langchain_id": (
            "channel_talk:document_article:channel-1:space-1:ko:article-1:chunk:0"
        ),
        "content": "article chunk",
        "source": "channel_talk",
        "entity_type": "document_article",
        "record_id": "article-1",
        "scope_type": "channel",
        "scope_id": "channel-1",
        "target_type": "document_space",
        "target_id": "space-1",
        "target_name": "Help Center",
        "title": "Article title",
        "body": "article chunk",
        "data": {"parts": []},
        "url": (
            "https://desk.channel.io/#/channels/channel-1/document_spaces/"
            "space-1/articles/article-1"
        ),
        "created_at": _dt(),
        "updated_at": _dt(),
        "synced_at": _dt(),
        "langchain_metadata": {
            "channel_talk_document_article": {
                "schema_version": 2,
                "author": {
                    "external_user_id": "manager-1",
                    "internal_user_id": "usr_manager_1",
                },
                "taxonomy": {
                    "topic_ids": [],
                    "topic_names": [],
                    "category_id": None,
                    "category_name": None,
                },
                "publication": {
                    "published_at": None,
                    "published_revision_id": None,
                    "current_revision_id": None,
                },
            }
        },
    }


def test_package_exports_channel_talk_validation_services() -> None:
    assert ChannelTalkArticleV2ValidationService.__name__
    assert ChannelTalkUserChatV2ValidationService.__name__
    assert JiraIssueV2ValidationService.__name__


def test_user_chat_count_validation_query_uses_hydrated_namespace_rows() -> None:
    query = str(build_channel_talk_user_chat_v2_count_validation_query())

    assert "WITH v1_user_chat AS" in query
    assert "WHERE source = 'channel_talk'" in query
    assert "entity_type = 'user_chat'" in query
    assert "missing_in_v2" in query
    assert "extra_in_v2" in query
    assert "? 'channel_talk_user_chat'" in query
    assert (
        "COALESCE(metadata::jsonb, '{}'::jsonb) - 'channel_talk_user_chat' = '{}'::jsonb"
        in query
    )


def test_document_article_count_validation_query_requires_current_schema() -> None:
    query = str(build_channel_talk_document_article_v2_count_validation_query())

    assert "WITH v1_article AS" in query
    assert "WHERE source = 'channel_talk'" in query
    assert "entity_type = 'document_article'" in query
    assert "? 'channel_talk_document_article'" in query
    assert (
        "COALESCE(metadata::jsonb, '{}'::jsonb) - 'channel_talk_document_article' = '{}'::jsonb"
        in query
    )
    assert "#>> '{channel_talk_document_article,schema_version}'" in query
    assert ") = '2'" in query


def test_user_chat_sample_query_returns_hydrated_rows_only() -> None:
    query = str(build_channel_talk_user_chat_v2_sample_query())

    assert "document_id AS langchain_id" in query
    assert "AS langchain_metadata" in query
    assert "WHERE source = 'channel_talk'" in query
    assert "entity_type = 'user_chat'" in query
    assert "? 'channel_talk_user_chat'" in query
    assert (
        "COALESCE(metadata::jsonb, '{}'::jsonb) - 'channel_talk_user_chat' = '{}'::jsonb"
        in query
    )


def test_document_article_sample_query_returns_current_schema_rows_only() -> None:
    query = str(build_channel_talk_document_article_v2_sample_query())

    assert "document_id AS langchain_id" in query
    assert "AS langchain_metadata" in query
    assert "WHERE source = 'channel_talk'" in query
    assert "entity_type = 'document_article'" in query
    assert "? 'channel_talk_document_article'" in query
    assert (
        "COALESCE(metadata::jsonb, '{}'::jsonb) - 'channel_talk_document_article' = '{}'::jsonb"
        in query
    )
    assert "#>> '{channel_talk_document_article,schema_version}'" in query
    assert ") = '2'" in query


def test_user_chat_sample_validator_accepts_hydrated_row() -> None:
    result = validate_channel_talk_user_chat_v2_sample_row(_valid_user_chat_row())

    assert result.langchain_id == "channel_talk:user_chat:channel-1:chat-1"
    assert result.is_valid is True
    assert result.errors == ()


def test_user_chat_sample_validator_rejects_seed_or_legacy_shape() -> None:
    row = _valid_user_chat_row()
    row["data"] = {}
    row["langchain_metadata"] = {
        "channel_talk_user_chat": {
            "state": "opened",
            "contextual_content": "legacy blob",
            "assignment": [],
        }
    }

    result = validate_channel_talk_user_chat_v2_sample_row(row)

    assert result.is_valid is False
    assert "missing:data.parts" in result.errors
    assert "forbidden:channel_talk_user_chat.contextual_content" in result.errors
    assert "invalid:channel_talk_user_chat.assignment" in result.errors


def test_document_article_sample_validator_accepts_hydrated_row() -> None:
    result = validate_channel_talk_document_article_v2_sample_row(
        _valid_document_article_row()
    )

    assert result.langchain_id == (
        "channel_talk:document_article:channel-1:space-1:ko:article-1:chunk:0"
    )
    assert result.is_valid is True
    assert result.errors == ()


def test_document_article_sample_validator_rejects_wrong_schema_or_namespace() -> None:
    row = _valid_document_article_row()
    row["langchain_metadata"] = {
        "contextual_content": "legacy blob",
        "channel_talk_document_article": {
            "schema_version": 1,
            "author": [],
            "taxonomy": {},
            "publication": {},
        },
    }

    result = validate_channel_talk_document_article_v2_sample_row(row)

    assert result.is_valid is False
    assert "invalid:metadata_namespace" in result.errors

    row = _valid_document_article_row()
    row["langchain_metadata"]["channel_talk_document_article"]["schema_version"] = 1
    row["langchain_metadata"]["channel_talk_document_article"]["author"] = []

    result = validate_channel_talk_document_article_v2_sample_row(row)

    assert "invalid:channel_talk_document_article.schema_version" in result.errors
    assert "invalid:channel_talk_document_article.author" in result.errors
