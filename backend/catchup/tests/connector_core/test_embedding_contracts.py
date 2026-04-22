from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase

from catchup.connector_core.document_format import ChannelTalkUserChatAnchorsMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatAssignmentMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatChatMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatChunkMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatCoreMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatCustomerMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatLogicalMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatMessageMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatMetricsMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatTagsMetadata
from catchup.connector_core.document_format import ChannelTalkUserChatTimingMetadata
from catchup.connector_core.document_format import DocumentBaseMetadata


class ChannelTalkUserChatLogicalMetadataTests(TestCase):
    def _build_contract(self) -> ChannelTalkUserChatLogicalMetadata:
        now = datetime(2026, 4, 22, 2, 10, tzinfo=timezone.utc)
        return ChannelTalkUserChatLogicalMetadata(
            base=DocumentBaseMetadata(
                source="channel_talk",
                record_id="chat-123",
                created_at=now,
                updated_at=now,
                synced_at=now,
                contextual_content="Conversation transcript",
            ),
            user_chat_core=ChannelTalkUserChatCoreMetadata(
                chat=ChannelTalkUserChatChatMetadata(
                    channel_id="channel-1",
                    user_chat_id="chat-123",
                    state="opened",
                ),
                customer=ChannelTalkUserChatCustomerMetadata(
                    user_id="user-1",
                    email="customer@example.com",
                ),
                assignment=ChannelTalkUserChatAssignmentMetadata(
                    manager_ids=["manager-1"],
                    assignee_id="manager-1",
                ),
                messages=ChannelTalkUserChatMessageMetadata(
                    message_ids=["message-1", "message-2"],
                    included_message_count=2,
                    excluded_message_count=1,
                    author_types=["user", "manager"],
                ),
                timing=ChannelTalkUserChatTimingMetadata(
                    opened_at=now,
                    desk_updated_at=now,
                ),
                metrics=ChannelTalkUserChatMetricsMetadata(
                    reply_count=1,
                ),
                anchors=ChannelTalkUserChatAnchorsMetadata(
                    desk_message_id="message-2",
                ),
                tags=ChannelTalkUserChatTagsMetadata(
                    keys=["vip"],
                    names=["VIP"],
                ),
                chunk=ChannelTalkUserChatChunkMetadata(
                    chunk_index=0,
                    chunk_count=1,
                ),
            ),
        )

    def test_contract_enforces_channel_talk_user_chat_identity(self) -> None:
        contract = self._build_contract()

        self.assertEqual(contract.base.source, "channel_talk")
        self.assertEqual(contract.base.record_id, "chat-123")
        self.assertEqual(contract.base.contextual_content, "Conversation transcript")
        self.assertEqual(contract.user_chat_core.chat.user_chat_id, "chat-123")

    def test_storage_projection_keeps_flat_shared_keys_and_nested_payload(self) -> None:
        contract = self._build_contract()

        storage = contract.to_storage_metadata()

        self.assertEqual(storage["source"], "channel_talk")
        self.assertEqual(storage["entity_type"], "user_chat")
        self.assertEqual(storage["contextual_content"], "Conversation transcript")
        self.assertEqual(storage["record_id"], "chat-123")
        self.assertEqual(storage["channel_id"], "channel-1")
        self.assertEqual(storage["user_chat_id"], "chat-123")
        self.assertEqual(storage["state"], "opened")
        self.assertEqual(storage["user_id"], "user-1")
        self.assertEqual(storage["assignee_id"], "manager-1")
        self.assertEqual(storage["chunk_index"], 0)
        self.assertEqual(storage["chunk_count"], 1)
        self.assertEqual(storage["tag_keys"], ["vip"])
        self.assertEqual(storage["tag_names"], ["VIP"])
        self.assertIn("base", storage)
        self.assertIn("user_chat_core", storage)

    def test_contract_rejects_record_id_mismatch(self) -> None:
        now = datetime(2026, 4, 22, 2, 10, tzinfo=timezone.utc)

        with self.assertRaisesRegex(ValueError, "base.record_id"):
            ChannelTalkUserChatLogicalMetadata(
                base=DocumentBaseMetadata(
                    source="channel_talk",
                    record_id="chat-999",
                    created_at=now,
                    updated_at=now,
                    synced_at=now,
                    contextual_content="Conversation transcript",
                ),
                user_chat_core=ChannelTalkUserChatCoreMetadata(
                    chat=ChannelTalkUserChatChatMetadata(
                        channel_id="channel-1",
                        user_chat_id="chat-123",
                        state="opened",
                    ),
                    customer=ChannelTalkUserChatCustomerMetadata(
                        user_id="user-1",
                    ),
                    assignment=ChannelTalkUserChatAssignmentMetadata(),
                    messages=ChannelTalkUserChatMessageMetadata(),
                    timing=ChannelTalkUserChatTimingMetadata(),
                    metrics=ChannelTalkUserChatMetricsMetadata(),
                    anchors=ChannelTalkUserChatAnchorsMetadata(),
                    tags=ChannelTalkUserChatTagsMetadata(),
                    chunk=ChannelTalkUserChatChunkMetadata(),
                ),
            )

    def test_contract_rejects_non_channel_talk_source(self) -> None:
        now = datetime(2026, 4, 22, 2, 10, tzinfo=timezone.utc)

        with self.assertRaisesRegex(ValueError, "base.source"):
            ChannelTalkUserChatLogicalMetadata(
                base=DocumentBaseMetadata(
                    source="slack",
                    record_id="chat-123",
                    created_at=now,
                    updated_at=now,
                    synced_at=now,
                    contextual_content="Conversation transcript",
                ),
                user_chat_core=ChannelTalkUserChatCoreMetadata(
                    chat=ChannelTalkUserChatChatMetadata(
                        channel_id="channel-1",
                        user_chat_id="chat-123",
                        state="opened",
                    ),
                    customer=ChannelTalkUserChatCustomerMetadata(
                        user_id="user-1",
                    ),
                    assignment=ChannelTalkUserChatAssignmentMetadata(),
                    messages=ChannelTalkUserChatMessageMetadata(),
                    timing=ChannelTalkUserChatTimingMetadata(),
                    metrics=ChannelTalkUserChatMetricsMetadata(),
                    anchors=ChannelTalkUserChatAnchorsMetadata(),
                    tags=ChannelTalkUserChatTagsMetadata(),
                    chunk=ChannelTalkUserChatChunkMetadata(),
                ),
            )
