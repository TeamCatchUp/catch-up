from __future__ import annotations

from catchup.sync.ingestion.vector_records import ChannelTalkUserChatV2RecordMapper
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _fetched_bundle
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _managers_by_id


def test_channel_talk_user_chat_v2_mapper_builds_contract_without_duplicates() -> None:
    bundle = _fetched_bundle()
    document = ChannelTalkUserChatV2RecordMapper().to_document(
        bundle,
        channel_id="channel-123",
        content="summarized support intent",
        managers_by_id=_managers_by_id(),
    )

    metadata = document.metadata
    domain_metadata = metadata["channel_talk_user_chat"]
    body = metadata["body"]
    parts = metadata["data"]["parts"]

    assert document.id == "channel_talk:user_chat:channel-123:chat-123"
    assert document.page_content == "summarized support intent"
    assert metadata["source"] == "channel_talk"
    assert metadata["entity_type"] == "user_chat"
    assert metadata["record_id"] == "chat-123"
    assert metadata["scope_type"] == "channel"
    assert metadata["scope_id"] == "channel-123"
    assert metadata["target_type"] == "channel"
    assert metadata["target_id"] == "channel-123"
    assert metadata["target_name"] == "Support"
    assert metadata["internal_author_id"] is None
    assert metadata["title"] == "VIP renewal help"

    assert "Hello from support" in body
    assert "private note" in body
    assert "Email: kim@example.com" in body
    assert "guide.pdf" in body
    assert "Choose an action" in body
    assert "Open" in body
    assert "Read the docs" in body
    assert "Support Guide" in body
    assert "Troubleshooting steps" in body
    assert "assign" not in body
    assert "https://example.com" not in body
    assert "channel-123" not in body
    assert "chat-123" not in body
    assert "Customer Kim" not in body

    assert {part["type"] for part in parts} >= {
        "message",
        "internal_note",
        "form_message",
        "system_event",
    }
    system_part = next(part for part in parts if part["type"] == "system_event")
    assert system_part["text"] == "assign"
    attachment_part = next(
        part
        for part in parts
        if part["metadata"].get("attachments")
    )
    assert "url" not in attachment_part["metadata"]["attachments"][0]

    assert set(domain_metadata) == {
        "state",
        "managed",
        "priority",
        "goal_state",
        "customer",
        "assignment",
        "messages",
        "timing",
        "metrics",
        "anchors",
        "tags",
    }
    for duplicated_field in (
        "channel_id",
        "channel_name",
        "user_chat_id",
        "source",
        "entity_type",
        "record_id",
        "scope_id",
        "target_id",
        "target_name",
    ):
        assert duplicated_field not in domain_metadata
    for derived_flag in (
        "has_internal_notes",
        "has_form_messages",
        "has_bot_messages",
        "has_system_events",
        "contains_private_events",
    ):
        assert derived_flag not in domain_metadata["messages"]
    assert "raw_payload" not in str(metadata)


def test_channel_talk_user_chat_v2_title_falls_back_to_customer_info() -> None:
    bundle = _fetched_bundle()
    detail = bundle.detail.model_copy(update={"description": None, "name": None})
    bundle = bundle.model_copy(update={"detail": detail})

    document = ChannelTalkUserChatV2RecordMapper().to_document(
        bundle,
        channel_id="channel-123",
        content="content",
    )

    assert document.metadata["title"] == "Customer Kim"
