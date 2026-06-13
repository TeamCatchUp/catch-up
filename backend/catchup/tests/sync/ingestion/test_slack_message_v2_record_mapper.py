from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.connectors.slack.schemas import SlackAttachment
from catchup.connectors.slack.schemas import SlackFileRef
from catchup.connectors.slack.schemas import SlackMessage
from catchup.connectors.slack.schemas import SlackReaction
from catchup.connectors.slack.schemas import SlackThreadReply
from catchup.sync.ingestion.vector_records.slack_message_mapper import (
    SlackMessageV2RecordMapper,
)


def _message() -> SlackMessage:
    return SlackMessage(
        ts="1712345678.000100",
        channel_id="C123",
        channel_name="general",
        url="https://acme.slack.com/archives/C123/p1712345678000100",
        message_type="thread_parent",
        text="Ship Slack message v2 migration",
        user_id="U123",
        user_name="hxxukii",
        user_real_name="Hxxukii",
        thread_ts="1712345678.000100",
        reply_count=1,
        latest_reply_ts="1712345699.000200",
        replies=[
            SlackThreadReply(
                ts="1712345699.000200",
                user_id="U456",
                user_name="teammate",
                text="Looks good after validation.",
                files=[
                    SlackFileRef(
                        id="F456",
                        name="validation.png",
                        title="Validation screenshot",
                        filetype="png",
                        mimetype="image/png",
                        pretty_type="PNG Image",
                        size=4096,
                        permalink="https://acme.slack.com/files/U456/F456/validation.png",
                        file_access="check_file_info",
                    )
                ],
            )
        ],
        reactions=[SlackReaction(name="eyes", count=2, users=["U456", "U789"])],
        files=[
            SlackFileRef(
                id="F123",
                name="migration-plan.md",
                title="Migration plan",
                filetype="markdown",
                mimetype="text/markdown",
                pretty_type="Markdown",
                size=184233,
                url_private="https://files.slack.com/files-pri/T123-F123/migration-plan.md",
                url_private_download="https://files.slack.com/files-pri/T123-F123/download/migration-plan.md",
                permalink="https://acme.slack.com/files/U123/F123/migration-plan.md",
                permalink_public="https://slack-files.com/T123-F123",
                preview="Migration plan preview",
                mode="hosted",
                file_access="visible",
            )
        ],
        attachments=[
            SlackAttachment(
                id=1,
                title="Backfill dashboard",
                title_link="https://example.test/backfill",
                text="Hydrate pending seed rows",
                service_name="Grafana",
                author_name="Observability",
                author_link="https://example.test/team/observability",
                color="#36c5f0",
                image_url="https://example.test/backfill.png",
                thumb_url="https://example.test/backfill-thumb.png",
                app_id="A123",
                app_unfurl_url="https://example.test/unfurl/backfill",
            )
        ],
        created_at=datetime(2024, 4, 5, 12, 34, 38, tzinfo=timezone.utc),
        edited_ts="1712345688.000150",
    )


def test_slack_message_v2_mapper_builds_normalized_row_contract() -> None:
    mapper = SlackMessageV2RecordMapper()

    document = mapper.to_document(
        _message(),
        team_id="T123",
        content="v1 summarized page content",
        internal_author_id="42",
        synced_at=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
    )

    assert document.id == "slack:message:T123:C123:1712345678.000100"
    assert document.page_content == "v1 summarized page content"
    assert document.metadata["source"] == "slack"
    assert document.metadata["entity_type"] == "message"
    assert document.metadata["record_id"] == "1712345678.000100"
    assert document.metadata["scope_type"] == "workspace"
    assert document.metadata["scope_id"] == "T123"
    assert document.metadata["target_type"] == "channel"
    assert document.metadata["target_id"] == "C123"
    assert document.metadata["target_name"] == "general"
    assert document.metadata["internal_author_id"] == "42"
    assert set(document.metadata["slack_message"]) == {
        "team_id",
        "channel_id",
        "channel_name",
        "ts",
        "thread_ts",
        "is_thread_root",
        "message_type",
        "subtype",
        "author",
        "reply_count",
        "reactions",
        "edited_at",
        "latest_reply_ts",
    }
    assert document.metadata["slack_message"]["author"] == {
        "slack_user_id": "U123",
        "slack_bot_id": None,
        "name": "Hxxukii",
        "catchup_user_id": "42",
    }
    assert document.metadata["slack_message"]["reactions"] == [
        {"name": "eyes", "count": 2}
    ]
    assert document.metadata["data"]["parts"] == [
        {
            "type": "message_body",
            "text": "Ship Slack message v2 migration",
            "metadata": {"message_type": "thread_parent"},
        },
        {
            "type": "thread_reply",
            "text": "Looks good after validation.",
            "metadata": {
                "ts": "1712345699.000200",
                "user_id": "U456",
                "user_name": "teammate",
                "reaction_count": 0,
                "file_count": 1,
            },
        },
        {
            "type": "attachment",
            "text": "Backfill dashboard\nHydrate pending seed rows",
            "metadata": {
                "id": 1,
                "title_link": "https://example.test/backfill",
                "author_name": "Observability",
                "author_link": "https://example.test/team/observability",
                "service_name": "Grafana",
                "color": "#36c5f0",
                "image_url": "https://example.test/backfill.png",
                "thumb_url": "https://example.test/backfill-thumb.png",
                "app_id": "A123",
                "app_unfurl_url": "https://example.test/unfurl/backfill",
            },
        },
        {
            "type": "file",
            "text": "Migration plan\nmigration-plan.md\nMigration plan preview",
            "metadata": {
                "id": "F123",
                "filetype": "markdown",
                "mimetype": "text/markdown",
                "pretty_type": "Markdown",
                "size": 184233,
                "mode": "hosted",
                "is_external": False,
                "file_access": "visible",
                "permalink": "https://acme.slack.com/files/U123/F123/migration-plan.md",
                "permalink_public": "https://slack-files.com/T123-F123",
                "url_private": "https://files.slack.com/files-pri/T123-F123/migration-plan.md",
                "url_private_download": "https://files.slack.com/files-pri/T123-F123/download/migration-plan.md",
                "parent_type": "message",
            },
        },
        {
            "type": "file",
            "text": "Validation screenshot\nvalidation.png",
            "metadata": {
                "id": "F456",
                "filetype": "png",
                "mimetype": "image/png",
                "pretty_type": "PNG Image",
                "size": 4096,
                "is_external": False,
                "file_access": "check_file_info",
                "permalink": "https://acme.slack.com/files/U456/F456/validation.png",
                "parent_type": "thread_reply",
                "reply_ts": "1712345699.000200",
            },
        },
    ]
    file_parts = [
        part for part in document.metadata["data"]["parts"] if part["type"] == "file"
    ]
    assert all("title" not in part["metadata"] for part in file_parts)
    assert all("name" not in part["metadata"] for part in file_parts)
    assert all("preview" not in part["metadata"] for part in file_parts)
    assert "contextual_content" not in document.metadata
    assert "files" not in document.metadata["slack_message"]
    assert "attachments" not in document.metadata["slack_message"]
