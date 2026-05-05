from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import TestCase

from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleArticleMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleAuthorMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleChunkMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleCoreMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleLogicalMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticlePublicationMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleSpaceMetadata,
)
from catchup.connector_core.document_format import (
    ChannelTalkDocumentArticleTaxonomyMetadata,
)
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
                    channel_name="Support",
                    user_chat_id="chat-123",
                    state="opened",
                    customer_name="VIP customer",
                    description="VIP onboarding question",
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
                    last_message_at=now,
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
        self.assertNotIn("base", storage)
        self.assertNotIn("channel_id", storage)
        self.assertNotIn("user_chat_id", storage)
        self.assertNotIn("included_message_count", storage)
        self.assertIn("user_chat_core", storage)
        self.assertEqual(
            storage["user_chat_core"]["chat"]["description"],
            "VIP onboarding question",
        )

    def test_storage_projection_falls_back_to_desk_updated_at(self) -> None:
        contract = self._build_contract()
        contract.base.updated_at = None

        storage = contract.to_storage_metadata()

        self.assertEqual(
            storage["updated_at"],
            contract.user_chat_core.timing.desk_updated_at.isoformat(),
        )

    def test_storage_projection_keeps_nested_message_datetimes_json_serialized(
        self,
    ) -> None:
        contract = self._build_contract()

        storage = contract.to_storage_metadata()

        self.assertEqual(
            storage["user_chat_core"]["messages"]["last_message_at"],
            "2026-04-22T02:10:00Z",
        )

    def test_storage_projection_includes_message_filter_flags(self) -> None:
        contract = self._build_contract()
        contract.user_chat_core.messages.contains_bot_messages = True
        contract.user_chat_core.messages.contains_private_events = True
        contract.user_chat_core.messages.contains_form_messages = True

        storage = contract.to_storage_metadata()

        message_metadata = storage["user_chat_core"]["messages"]
        self.assertEqual(message_metadata["included_message_count"], 2)
        self.assertEqual(message_metadata["excluded_message_count"], 1)
        self.assertTrue(message_metadata["contains_bot_messages"])
        self.assertTrue(message_metadata["contains_private_events"])
        self.assertTrue(message_metadata["contains_form_messages"])

    def test_customer_metadata_allows_missing_user_id(self) -> None:
        contract = self._build_contract()
        contract.user_chat_core.customer.user_id = None

        storage = contract.to_storage_metadata()

        self.assertIsNone(contract.user_chat_core.customer.user_id)
        self.assertIsNone(storage["user_chat_core"]["customer"]["user_id"])

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
                        channel_name="Support",
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
                        channel_name="Support",
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


class ChannelTalkDocumentArticleLogicalMetadataTests(TestCase):
    def _build_contract(self) -> ChannelTalkDocumentArticleLogicalMetadata:
        now = datetime(2026, 4, 22, 2, 10, tzinfo=timezone.utc)
        return ChannelTalkDocumentArticleLogicalMetadata(
            base=DocumentBaseMetadata(
                source="channel_talk",
                record_id="article-123",
                url="https://docs.example.com/refund",
                created_at=now,
                updated_at=now,
                synced_at=now,
                contextual_content="Refund draft",
            ),
            document_article_core=ChannelTalkDocumentArticleCoreMetadata(
                article=ChannelTalkDocumentArticleArticleMetadata(
                    article_id="article-123",
                    language="ko",
                    state="draft",
                    title="Refund draft",
                    url="https://docs.example.com/refund",
                ),
                space=ChannelTalkDocumentArticleSpaceMetadata(
                    channel_id="channel-1",
                    space_id="space-1",
                    channel_name="Support",
                    space_name="Help Center",
                ),
                author=ChannelTalkDocumentArticleAuthorMetadata(
                    author_id="author-1",
                    author_name="Writer",
                ),
                taxonomy=ChannelTalkDocumentArticleTaxonomyMetadata(
                    topic_ids=["topic-1"],
                    topic_names=["Billing"],
                    category_id="category-1",
                    category_name="Payments",
                ),
                publication=ChannelTalkDocumentArticlePublicationMetadata(
                    created_at=now,
                    updated_at=now,
                    published_at=None,
                    published_revision_id="revision-1",
                    current_revision_id="revision-2",
                ),
                chunk=ChannelTalkDocumentArticleChunkMetadata(
                    chunk_index=0,
                    chunk_count=2,
                ),
            ),
        )

    def test_contract_enforces_channel_talk_article_identity(self) -> None:
        contract = self._build_contract()

        self.assertEqual(contract.base.source, "channel_talk")
        self.assertEqual(contract.base.record_id, "article-123")
        self.assertEqual(
            contract.document_article_core.article.article_id,
            "article-123",
        )
        self.assertEqual(contract.document_article_core.article.state, "draft")

    def test_storage_projection_includes_article_state_and_nested_payload(self) -> None:
        contract = self._build_contract()

        storage = contract.to_storage_metadata()

        self.assertEqual(storage["source"], "channel_talk")
        self.assertEqual(storage["entity_type"], "document_article")
        self.assertEqual(storage["record_id"], "article-123")
        self.assertIn("document_article_core", storage)
        self.assertNotIn("article_state", storage)
        self.assertNotIn("channel_id", storage)
        self.assertNotIn("publication", storage)
        self.assertNotIn("chunk", storage)
        article_core = storage["document_article_core"]
        self.assertEqual(
            article_core["article"]["title"],
            "Refund draft",
        )
        self.assertEqual(article_core["space"]["channel_id"], "channel-1")
        self.assertEqual(article_core["space"]["space_id"], "space-1")
        self.assertEqual(article_core["space"]["channel_name"], "Support")
        self.assertEqual(article_core["space"]["space_name"], "Help Center")
        self.assertEqual(article_core["author"]["author_name"], "Writer")
        self.assertEqual(article_core["taxonomy"]["category_name"], "Payments")
        self.assertEqual(article_core["chunk"]["chunk_index"], 0)
        self.assertEqual(article_core["chunk"]["chunk_count"], 2)
        self.assertNotIn("summary", article_core["article"])
        self.assertEqual(
            article_core["publication"]["updated_at"],
            "2026-04-22T02:10:00Z",
        )

    def test_contract_rejects_chunk_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "chunk_index"):
            ChannelTalkDocumentArticleChunkMetadata(
                chunk_index=2,
                chunk_count=2,
            )

    def test_contract_rejects_record_id_mismatch(self) -> None:
        contract = self._build_contract()

        with self.assertRaisesRegex(ValueError, "base.record_id"):
            ChannelTalkDocumentArticleLogicalMetadata(
                base=contract.base.model_copy(update={"record_id": "other"}),
                document_article_core=contract.document_article_core,
            )

    def test_contract_rejects_non_channel_talk_source(self) -> None:
        contract = self._build_contract()

        with self.assertRaisesRegex(ValueError, "base.source"):
            ChannelTalkDocumentArticleLogicalMetadata(
                base=contract.base.model_copy(update={"source": "slack"}),
                document_article_core=contract.document_article_core,
            )
