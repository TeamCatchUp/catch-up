from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase

from catchup.db.models import SyncConnector
from catchup.sync.incremental.resolve.channel_talk import (
    resolve_channel_talk_user_chat_event,
)


class ResolveChannelTalkEventTests(TestCase):
    def test_message_payload_returns_user_chat_record_change(self) -> None:
        result = resolve_channel_talk_user_chat_event(
            trusted_channel_id="channel-123",
            payload={
                "type": "message",
                "entity": {
                    "channelId": "channel-123",
                    "chatType": "userChat",
                    "chatId": "user-chat-123",
                    "createdAt": "2026-04-25T08:30:00Z",
                },
            },
        )

        self.assertEqual(len(result.changes), 1)
        change = result.changes[0]
        self.assertEqual(change.connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(change.scope_id, "channel-123")
        self.assertEqual(change.parent_type, "channel")
        self.assertEqual(change.parent_id, "channel-123")
        self.assertEqual(change.record_type, "user_chat")
        self.assertEqual(change.record_id, "user-chat-123")
        self.assertEqual(change.event_kind, "updated")
        self.assertEqual(
            change.last_event_at,
            datetime(2026, 4, 25, 8, 30, tzinfo=timezone.utc),
        )

    def test_user_chat_payload_returns_user_chat_record_change(self) -> None:
        result = resolve_channel_talk_user_chat_event(
            trusted_channel_id="channel-123",
            payload={
                "type": "userChat",
                "entity": {
                    "channelId": "channel-123",
                    "id": "user-chat-456",
                    "updatedAt": 1777105800000,
                },
            },
        )

        self.assertEqual(len(result.changes), 1)
        change = result.changes[0]
        self.assertEqual(change.scope_id, "channel-123")
        self.assertEqual(change.parent_type, "channel")
        self.assertEqual(change.parent_id, "channel-123")
        self.assertEqual(change.record_type, "user_chat")
        self.assertEqual(change.record_id, "user-chat-456")

    def test_unsupported_payload_shape_returns_no_record_changes(self) -> None:
        result = resolve_channel_talk_user_chat_event(
            trusted_channel_id="channel-123",
            payload={
                "type": "manager",
                "entity": {
                    "id": "manager-123",
                },
            },
        )

        self.assertEqual(result.changes, [])
        self.assertEqual(result.reason, "unsupported_type")
