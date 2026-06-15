from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.connectors.slack.schemas import SlackAttachment
from catchup.connectors.slack.schemas import SlackFileRef
from catchup.connectors.slack.schemas import SlackMessage
from catchup.connectors.slack.schemas import SlackReaction
from catchup.connectors.slack.schemas import SlackThreadReply
from catchup.connectors.slack.schemas import SlackUser
from catchup.sync.ingestion.document_builders.slack import SlackTransformer
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
        text=(
            "legacy extracted content should not be used for v2 title "
            "when raw_text is available"
        ),
        raw_text=(
            "Ship Slack message v2 migration with the full parent message retained "
            "without preview truncation for <@U456>"
        ),
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
                user_real_name="Teammate",
                text="Looks good after validation, <@U123>.",
                files=[
                    SlackFileRef(
                        id="F456",
                        name="validation.png",
                        title="Validation screenshot",
                        filetype="png",
                        mimetype="image/png",
                        pretty_type="PNG Image",
                        size=4096,
                        preview_plain_text="Reply file plain text for <@U123>",
                        permalink="https://acme.slack.com/files/U456/F456/validation.png",
                        file_access="check_file_info",
                    )
                ],
                attachments=[
                    SlackAttachment(
                        id=2,
                        title="Reply attachment",
                        text="Reply attachment detail for <@U123>",
                    )
                ],
                blocks=[
                    {
                        "type": "section",
                        "block_id": "reply-section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Reply block detail for <@U123>",
                        },
                    }
                ],
            )
        ],
        reactions=[SlackReaction(name="eyes", count=2, users=["U456", "U789"])],
        mentioned_users=[
            SlackUser(id="U456", name="teammate", real_name="Teammate"),
        ],
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
                preview="Migration plan preview for <@U456>",
                preview_plain_text="Migration plan plain preview for <@U456>",
                plain_text="Migration plan extracted file text",
                initial_comment="Initial file comment for <@U456>",
                mode="hosted",
                file_access="visible",
            )
        ],
        attachments=[
            SlackAttachment(
                id=1,
                title="Backfill dashboard",
                title_link="https://example.test/backfill",
                text="Hydrate pending seed rows for <@U456>",
                fields=[
                    {"title": "Owner", "value": "<@U456>", "short": True},
                ],
                service_name="Grafana",
                author_name="Observability",
                author_link="https://example.test/team/observability",
                color="#36c5f0",
                image_url="https://example.test/backfill.png",
                thumb_url="https://example.test/backfill-thumb.png",
                app_id="A123",
                app_unfurl_url="https://example.test/unfurl/backfill",
                blocks=[
                    {
                        "type": "section",
                        "block_id": "attachment-section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Attachment block detail for <@U456>",
                        },
                    }
                ],
            )
        ],
        blocks=[
            {
                "type": "section",
                "block_id": "message-section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Message block detail for <@U456>",
                },
            }
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
    assert document.metadata["title"] == (
        "Ship Slack message v2 migration with the full parent message retained "
        "without preview truncation for @Teammate"
    )
    assert document.metadata["body"] == (
        "Looks good after validation, @Hxxukii.\n\n"
        "Backfill dashboard\n"
        "Hydrate pending seed rows for @Teammate\n"
        "Owner: @Teammate\n\n"
        "Attachment block detail for @Teammate\n\n"
        "Message block detail for @Teammate\n\n"
        "Migration plan\n"
        "migration-plan.md\n"
        "Migration plan plain preview for @Teammate\n"
        "Migration plan extracted file text\n"
        "Migration plan preview for @Teammate\n"
        "Initial file comment for @Teammate\n\n"
        "Reply attachment\n"
        "Reply attachment detail for @Hxxukii\n\n"
        "Validation screenshot\n"
        "validation.png\n"
        "Reply file plain text for @Hxxukii\n\n"
        "Reply block detail for @Hxxukii"
    )
    assert "Ship Slack message v2 migration" not in document.metadata["body"]
    assert "Hydrate pending seed rows" in document.metadata["body"]
    assert set(document.metadata["slack_message"]) == {
        "team_id",
        "channel_id",
        "channel_name",
        "ts",
        "message_type",
        "subtype",
        "author",
        "reactions",
        "edited_at",
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
            "text": (
                "Ship Slack message v2 migration with the full parent message retained "
                "without preview truncation for @Teammate"
            ),
            "metadata": {"message_type": "thread_parent"},
        },
        {
            "type": "thread_reply",
            "text": "Looks good after validation, @Hxxukii.",
            "metadata": {
                "ts": "1712345699.000200",
                "user_id": "U456",
                "user_name": "Teammate",
                "reaction_count": 0,
                "file_count": 1,
            },
        },
        {
            "type": "attachment",
            "text": (
                "Backfill dashboard\n"
                "Hydrate pending seed rows for @Teammate\n"
                "Owner: @Teammate"
            ),
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
                "parent_type": "message",
            },
        },
        {
            "type": "block_text",
            "text": "Attachment block detail for @Teammate",
            "metadata": {
                "block_type": "section",
                "block_id": "attachment-section",
                "parent_type": "attachment",
                "attachment_id": "1",
            },
        },
        {
            "type": "block_text",
            "text": "Message block detail for @Teammate",
            "metadata": {
                "block_type": "section",
                "block_id": "message-section",
                "parent_type": "message",
            },
        },
        {
            "type": "file",
            "text": (
                "Migration plan\n"
                "migration-plan.md\n"
                "Migration plan plain preview for @Teammate\n"
                "Migration plan extracted file text\n"
                "Migration plan preview for @Teammate\n"
                "Initial file comment for @Teammate"
            ),
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
            "type": "attachment",
            "text": "Reply attachment\nReply attachment detail for @Hxxukii",
            "metadata": {
                "id": 2,
                "parent_type": "thread_reply",
                "reply_ts": "1712345699.000200",
            },
        },
        {
            "type": "file",
            "text": (
                "Validation screenshot\n"
                "validation.png\n"
                "Reply file plain text for @Hxxukii"
            ),
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
        {
            "type": "block_text",
            "text": "Reply block detail for @Hxxukii",
            "metadata": {
                "block_type": "section",
                "block_id": "reply-section",
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


def test_slack_message_v2_mapper_decodes_literal_unicode_display_values() -> None:
    mapper = SlackMessageV2RecordMapper()
    message = SlackMessage(
        ts="1712345678.000100",
        channel_id="C123",
        channel_name="\\uac1c\\ubc1c\\ud300",
        message_type="standard",
        text="안녕하세요",
        user_id="U123",
        user_name="hxxukii",
        user_real_name="\\uc2e0\\ud601",
        thread_ts="1712345678.000100",
        created_at=datetime(2024, 4, 5, 12, 34, 38, tzinfo=timezone.utc),
    )

    document = mapper.to_document(
        message,
        team_id="T123",
        content="v1 summarized page content",
        synced_at=datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc),
    )

    assert document.metadata["target_name"] == "개발팀"
    assert document.metadata["slack_message"]["channel_name"] == "개발팀"
    assert document.metadata["slack_message"]["author"]["name"] == "팀원A"


def test_slack_transformer_preserves_api_fields_for_v2_parts() -> None:
    transformer = SlackTransformer.from_user_names({"U123": "Hxxukii"})

    message = transformer.parse_message(
        {
            "ts": "1712345678.000100",
            "text": "Parent raw text",
            "user": "U123",
            "files": [
                {
                    "id": "F123",
                    "name": "plan.md",
                    "title": "Plan",
                    "preview": "mrkdwn preview",
                    "preview_plain_text": "plain preview",
                    "plain_text": "extracted plain text",
                    "initial_comment": "initial comment",
                }
            ],
            "attachments": [
                {
                    "id": 1,
                    "title": "Attachment title",
                    "text": "Attachment text",
                    "blocks": [
                        {
                            "type": "section",
                            "block_id": "attachment-block",
                            "text": {"type": "mrkdwn", "text": "Attachment block"},
                        }
                    ],
                }
            ],
            "blocks": [
                {
                    "type": "section",
                    "block_id": "message-block",
                    "text": {"type": "mrkdwn", "text": "Message block"},
                }
            ],
        },
        channel_id="C123",
        channel_name="general",
    )

    assert message.raw_text == "Parent raw text"
    assert message.blocks == [
        {
            "type": "section",
            "block_id": "message-block",
            "text": {"type": "mrkdwn", "text": "Message block"},
        }
    ]
    assert message.files[0].preview_plain_text == "plain preview"
    assert message.files[0].plain_text == "extracted plain text"
    assert message.attachments[0].blocks[0]["block_id"] == "attachment-block"
