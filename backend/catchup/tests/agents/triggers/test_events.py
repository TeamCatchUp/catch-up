from datetime import datetime
from datetime import timezone

from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.events import normalize_verified_connector_event
from catchup.connector_core.domain.webhooks import VerifiedConnectorWebhookEvent


def test_agent_webhook_event_carries_normalized_webhook_envelope() -> None:
    event = AgentWebhookEvent(
        event_id="channel_talk:user_chat.new_message:stable-id",
        source="channel_talk",
        event_type="user_chat.new_message",
        occurred_at=datetime(2026, 5, 28, 1, 0, tzinfo=timezone.utc),
        payload={"event": "push", "entity": {"channelId": "ch-001"}},
    )

    assert event.event_id == "channel_talk:user_chat.new_message:stable-id"
    assert event.external_event_id is None
    assert event.payload["entity"]["channelId"] == "ch-001"
    assert event.received_at.tzinfo is not None


def test_channel_talk_normalizer_maps_message_push_to_new_message() -> None:
    payload = {
        "event": "push",
        "type": "message",
        "entity": {
            "channelId": "payload-channel",
            "chatType": "userChat",
            "chatId": "chat-1",
            "id": "message-1",
            "createdAt": 1776825600000,
        },
    }
    result = normalize_verified_connector_event(
        VerifiedConnectorWebhookEvent(
            source="channel_talk",
            event_type="message",
            payload=payload,
        )
    )

    assert result.event is not None
    assert result.event.event_id.startswith("channel_talk:user_chat.new_message:")
    assert result.event.external_event_id is None
    assert result.event.event_type == "user_chat.new_message"
    assert result.event.payload == payload


def test_channel_talk_normalizer_maps_user_chat_push_to_created_with_referred_message() -> None:
    payload = {
        "event": "push",
        "type": "userChat",
        "entity": {
            "id": "chat-1",
            "channelId": "payload-channel",
            "createdAt": 1776825600000,
        },
        "refers": {
            "message": {
                "id": "message-1",
                "channelId": "payload-channel",
                "chatType": "userChat",
                "chatId": "chat-1",
                "createdAt": 1776825600000,
            },
        },
    }
    result = normalize_verified_connector_event(
        VerifiedConnectorWebhookEvent(
            source="channel_talk",
            event_type="userChat",
            payload=payload,
        )
    )

    assert result.event is not None
    assert result.event.event_id.startswith("channel_talk:user_chat.created:")
    assert result.event.external_event_id is None
    assert result.event.event_type == "user_chat.created"
    assert result.event.payload == payload


def test_channel_talk_normalizer_ignores_non_user_chat_message() -> None:
    result = normalize_verified_connector_event(
        VerifiedConnectorWebhookEvent(
            source="channel_talk",
            event_type="message",
            payload={
                "event": "push",
                "type": "message",
                "entity": {
                    "channelId": "payload-channel",
                    "chatType": "group",
                    "chatId": "chat-1",
                    "id": "message-1",
                },
            },
        )
    )

    assert result.event is None
    assert result.ignored_reason == "unsupported_chat_type"


def test_channel_talk_normalizer_rejects_non_documented_type_aliases() -> None:
    result = normalize_verified_connector_event(
        VerifiedConnectorWebhookEvent(
            source="channel_talk",
            event_type="user_chat",
            payload={
                "event": "push",
                "type": "user_chat",
                "entity": {
                    "id": "chat-1",
                    "channelId": "payload-channel",
                },
            },
        )
    )

    assert result.event is None
    assert result.ignored_reason == "unsupported_event_type"


def test_channel_talk_normalizer_requires_payload_channel_id() -> None:
    result = normalize_verified_connector_event(
        VerifiedConnectorWebhookEvent(
            source="channel_talk",
            event_type="message",
            payload={
                "event": "push",
                "type": "message",
                "entity": {
                    "chatType": "userChat",
                    "chatId": "chat-1",
                },
            },
        )
    )

    assert result.event is None
    assert result.ignored_reason == "missing_channel_id"


def test_channel_talk_message_requires_chat_id_not_message_id() -> None:
    result = normalize_verified_connector_event(
        VerifiedConnectorWebhookEvent(
            source="channel_talk",
            event_type="message",
            payload={
                "event": "push",
                "type": "message",
                "entity": {
                    "channelId": "payload-channel",
                    "chatType": "userChat",
                    "id": "message-1",
                },
            },
        )
    )

    assert result.event is None
    assert result.ignored_reason == "missing_user_chat_id"
