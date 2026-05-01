from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from pydantic import ValidationError

from catchup.connector_core.adapters.channel_talk.article_full_sync import (
    ChannelTalkArticleFullSyncAdapter,
)
from catchup.connector_core.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncAdapter,
)
from catchup.connector_core.application.full_sync import ConnectorFullSyncApplication
from catchup.connector_core.descriptors.channel_talk import CHANNEL_TALK_DESCRIPTOR
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkFetchedUserChat,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkFetchedUserChatsResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncCheckpoint,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncExecutionRequest,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncExecutionResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncFetchResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncPersistResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncSummaryResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncTransformResult,
)
from catchup.connectors.channel_talk.core.user_chat_message_renderer import (
    UserChatMessageRenderer,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    DEFAULT_ARTICLE_FULL_SYNC_STATES,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncExecutionResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncFetchResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncPersistResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncSummaryResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncTransformResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkFetchedArticle,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkFetchedArticlesResult,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_DISPLAY_NAME,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    ChannelTalkFullSyncTargetPlan,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleRevision,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleRevisionView,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext


def _window() -> FullSyncWindow:
    return FullSyncWindow(
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
    )


def _connection() -> ChannelTalkCredentialsRecord:
    return ChannelTalkCredentialsRecord(
        channel_id="channel-123",
        channel_name="Support",
        access_key="access-key",
        access_secret="access-secret",
        webhook_token="webhook-token",
    )


def _document_connection() -> ChannelTalkDocumentCredentialsRecord:
    return ChannelTalkDocumentCredentialsRecord(
        channel_id="channel-123",
        space_id="space-123",
        space_name="Help Center",
        access_key="documents-access-key",
        access_secret="documents-access-secret",
        association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
    )


def _fetched_bundle() -> ChannelTalkFetchedUserChat:
    detail = ChannelTalkUserChatDetail.from_api_payload(
        {
            "id": "chat-123",
            "channelId": "channel-123",
            "state": "opened",
            "name": "VIP onboarding",
            "description": "VIP renewal help",
            "priority": "urgent",
            "goalState": "resolved",
            "assignee": {
                "id": "manager-1",
                "name": "Agent Lee",
                "email": "lee@example.com",
            },
            "managerIds": ["manager-1", "manager-2"],
            "tags": [{"key": "vip", "name": "VIP"}],
            "createdAt": "2026-04-21T09:00:00Z",
            "deskUpdatedAt": "2026-04-21T09:30:00Z",
            "user": {
                "id": "user-123",
                "memberId": "member-123",
                "name": "Customer Kim",
                "email": "kim@example.com",
            },
        },
        user_chat_id="chat-123",
    )
    public_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-1",
            "chatId": "chat-123",
            "personType": "manager",
            "manager": {"id": "manager-1", "name": "Agent Lee"},
            "plainText": "Hello from support",
            "createdAt": "2026-04-21T09:00:00Z",
        },
        user_chat_id="chat-123",
    )
    private_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-2",
            "chatId": "chat-123",
            "personType": "manager",
            "personId": "manager-1",
            "text": "private note",
            "private": True,
            "createdAt": "2026-04-21T09:05:00Z",
        },
        user_chat_id="chat-123",
    )
    form_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-3",
            "chatId": "chat-123",
            "personType": "user",
            "user": {"id": "user-123", "memberId": "member-123"},
            "form": {
                "type": "lead",
                "inputs": [{"label": "Email", "value": "kim@example.com"}],
            },
            "createdAt": "2026-04-21T09:06:00Z",
        },
        user_chat_id="chat-123",
    )
    file_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-4",
            "chatId": "chat-123",
            "personType": "manager",
            "personId": "manager-2",
            "files": [
                {
                    "key": "file-1",
                    "name": "guide.pdf",
                    "contentType": "application/pdf",
                }
            ],
            "createdAt": "2026-04-21T09:07:00Z",
        },
        user_chat_id="chat-123",
    )
    button_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-5",
            "chatId": "chat-123",
            "personType": "manager",
            "personId": "manager-1",
            "plainText": "Choose an action",
            "buttons": [
                {
                    "text": "Open",
                    "url": "https://example.com",
                }
            ],
            "createdAt": "2026-04-21T09:08:00Z",
        },
        user_chat_id="chat-123",
    )
    system_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-6",
            "chatId": "chat-123",
            "personType": "manager",
            "personId": "manager-1",
            "log": {"action": "assign"},
            "private": True,
            "createdAt": "2026-04-21T09:09:00Z",
        },
        user_chat_id="chat-123",
    )
    web_page_message = ChannelTalkUserChatMessage.from_api_payload(
        {
            "id": "msg-7",
            "chatId": "chat-123",
            "personType": "manager",
            "personId": "manager-1",
            "plainText": "Read the docs",
            "webPage": {
                "title": "Support Guide",
                "url": "https://example.com/guide",
                "description": "Troubleshooting steps",
            },
            "createdAt": "2026-04-21T09:10:00Z",
        },
        user_chat_id="chat-123",
    )
    return ChannelTalkFetchedUserChat(
        state=ChannelTalkUserChatState.OPENED,
        list_item=ChannelTalkUserChatListItem(
            user_chat_id="chat-123",
            state=ChannelTalkUserChatState.OPENED,
            user_id="user-123",
            member_id="member-123",
            ordering_marker=datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc),
        ),
        detail=detail,
        messages=(
            public_message,
            private_message,
            form_message,
            file_message,
            button_message,
            system_message,
            web_page_message,
        ),
    )


def _managers_by_id() -> dict[str, ChannelTalkManagerMetadata]:
    return {
        "manager-1": ChannelTalkManagerMetadata(
            manager_id="manager-1",
            name="Agent Lee",
            email="lee@example.com",
            role_id="role-1",
        ),
        "manager-2": ChannelTalkManagerMetadata(
            manager_id="manager-2",
            name="Agent Park",
            email="park@example.com",
            role_id="role-2",
        ),
    }


class _FakeSummarizer:
    def __init__(
        self,
        *,
        summaries: list[str] | None = None,
    ) -> None:
        self.summaries = summaries or ["summarized support intent"]
        self.requests = []
        self.audit_context = None
        self.context = None

    async def summarize_batch(
        self,
        requests,
        max_concurrent=50,
        audit_context=None,
        context=None,
    ):
        _ = max_concurrent
        self.requests = list(requests)
        self.audit_context = audit_context
        self.context = context
        return list(self.summaries)


class _FakeRepository:
    def __init__(self) -> None:
        self.deleted_ids: list[str] = []
        self.deleted_prefixes: list[str] = []
        self.added_documents = []
        self._initialized = False

    def ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("not initialized")

    async def initialize(self, _ensure_indices) -> None:
        self._initialized = True

    async def delete_documents(self, ids: list[str]) -> None:
        self.deleted_ids = list(ids)

    async def delete_by_id_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)

    async def add_documents(self, documents, ids=None):
        self.added_documents = list(documents)
        return list(ids or [])


class ChannelTalkFullSyncContractTests(TestCase):
    def test_checkpoint_accepts_vendor_user_chat_state_enum(self) -> None:
        checkpoint = ChannelTalkUserChatFullSyncCheckpoint(
            tenant_id="channel-123",
            state=ChannelTalkUserChatState.OPENED,
            window=_window(),
        )

        self.assertEqual(checkpoint.state, ChannelTalkUserChatState.OPENED)

    def test_web_page_only_message_renders_web_page_context_once(self) -> None:
        message = ChannelTalkUserChatMessage.from_api_payload(
            {
                "id": "msg-web",
                "chatId": "chat-123",
                "personType": "manager",
                "webPage": {
                    "title": "Support Guide",
                    "url": "https://example.com/guide",
                    "description": "Troubleshooting steps",
                },
            },
            user_chat_id="chat-123",
        )

        self.assertEqual(
            UserChatMessageRenderer.render_message_content(message),
            "Support Guide\nhttps://example.com/guide\nTroubleshooting steps",
        )

    def test_execution_request_exposes_explicit_channel_talk_user_chat_contract(
        self,
    ) -> None:
        execution = ChannelTalkUserChatFullSyncExecutionRequest(
            tenant_id="channel-123",
        )

        self.assertEqual(execution.connector, ConnectorKey.CHANNEL_TALK)
        self.assertEqual(execution.channel_id, "channel-123")
        self.assertEqual(execution.target, "user_chat")
        self.assertNotIn("stage", execution.model_dump())
        self.assertNotIn("states", execution.model_dump())
        self.assertNotIn("window", execution.model_dump())

    def test_execution_request_rejects_blank_tenant_id(self) -> None:
        with self.assertRaisesRegex(ValidationError, "tenant_id is required"):
            ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id=" ",
            )

    def test_window_rejects_inverted_bounds(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "window_start must be less than or equal to window_end",
        ):
            FullSyncWindow(
                window_start=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                window_end=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
            )

    def test_execution_request_keeps_only_tenant_checkpoint_alignment(self) -> None:
        with self.assertRaisesRegex(ValidationError, "checkpoint.tenant_id"):
            ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id="channel-123",
                checkpoint=ChannelTalkUserChatFullSyncCheckpoint(
                    tenant_id="other-channel",
                    state=ChannelTalkUserChatState.OPENED,
                    window=_window(),
                ),
            )

    def test_checkpoint_remains_target_scoped_without_redundant_stage(self) -> None:
        checkpoint = ChannelTalkUserChatFullSyncCheckpoint(
            tenant_id="channel-123",
            state=ChannelTalkUserChatState.OPENED,
            window=_window(),
            next_cursor="cursor-1",
        )

        self.assertEqual(checkpoint.target, "user_chat")
        self.assertNotIn("stage", checkpoint.model_dump())

    def test_descriptor_exposes_channel_talk_full_sync_targets(self) -> None:
        descriptor = CHANNEL_TALK_DESCRIPTOR

        self.assertTrue(descriptor.runtime.supports_full_sync)
        self.assertEqual(
            descriptor.runtime.targets,
            (
                CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
                CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
            ),
        )

    def test_document_space_plan_metadata_describes_real_target(self) -> None:
        metadata = ChannelTalkFullSyncTargetPlan.document_space(
            channel_id=" channel-123 ",
            space_id="space-123",
            space_name="Help Center",
        ).to_metadata()

        self.assertEqual(
            metadata,
            {
                "target_kind": "channel_talk.document_space",
                "channel_id": "channel-123",
                "space_id": "space-123",
                "space_name": "Help Center",
            },
        )

    def test_document_space_plan_rejects_blank_channel_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "channel_id is required"):
            ChannelTalkFullSyncTargetPlan.document_space(
                channel_id=" ",
                space_id="space-123",
                space_name="Help Center",
            )

    def test_article_display_name_contract(self) -> None:
        self.assertEqual(CHANNEL_TALK_DOCUMENT_ARTICLE_DISPLAY_NAME, "article")

    def test_channel_target_plan_metadata_describes_real_target(self) -> None:
        self.assertEqual(
            ChannelTalkFullSyncTargetPlan.channel(
                channel_id="channel-123",
                channel_name="Support",
            ).to_metadata(),
            {
                "target_kind": "channel_talk.channel",
                "channel_id": "channel-123",
            },
        )

    def test_channel_target_plan_separates_public_and_runtime_target(self) -> None:
        plan = ChannelTalkFullSyncTargetPlan.channel(
            channel_id="channel-123",
            channel_name="Support",
        )

        self.assertEqual(plan.target_type, "channel")
        self.assertEqual(plan.target_id, "channel-123")
        self.assertEqual(plan.target_name, "Support")
        self.assertEqual(plan.runtime_target, "user_chat")
        self.assertEqual(plan.channel_id, "channel-123")
        self.assertIsNone(plan.space_id)
        self.assertEqual(
            plan.to_metadata(),
            {
                "target_kind": "channel_talk.channel",
                "channel_id": "channel-123",
            },
        )

    def test_document_space_target_plan_separates_public_and_runtime_target(
        self,
    ) -> None:
        plan = ChannelTalkFullSyncTargetPlan.document_space(
            channel_id="channel-123",
            space_id="space-123",
            space_name="Help Center",
        )

        self.assertEqual(plan.target_type, "space")
        self.assertEqual(plan.target_id, "space-123")
        self.assertEqual(plan.target_name, "Help Center")
        self.assertEqual(plan.runtime_target, "document_article")
        self.assertEqual(plan.channel_id, "channel-123")
        self.assertEqual(plan.space_id, "space-123")
        self.assertEqual(
            plan.to_metadata(),
            {
                "target_kind": "channel_talk.document_space",
                "channel_id": "channel-123",
                "space_id": "space-123",
                "space_name": "Help Center",
            },
        )

    def test_target_plan_rejects_misaligned_public_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "channel target_id must match"):
            ChannelTalkFullSyncTargetPlan(
                target_type="channel",
                target_id="space-123",
                target_name="Support",
                runtime_target="user_chat",
                target_kind="channel_talk.channel",
                channel_id="channel-123",
            )


class ChannelTalkArticleFullSyncApplicationTests(IsolatedAsyncioTestCase):
    async def test_document_article_application_fetches_transforms_and_persists_articles(
        self,
    ) -> None:
        article_bundle = ChannelTalkFetchedArticle(
            language="ko",
            list_item=ChannelTalkDocumentArticle(
                article_id="article-1",
                state=ChannelTalkDocumentArticleState.DRAFT,
                title="Article draft",
                slug="published-article-23bb29b0",
                published_revision_id="published-revision-1",
            ),
            published_revision=ChannelTalkDocumentArticleRevisionView(
                revision=ChannelTalkDocumentArticleRevision(
                    revision_id="published-revision-1",
                    article_id="article-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    title="Published article",
                    body_html="<p>Published body</p>",
                )
            ),
        )
        fake_repository = _FakeRepository()
        fake_fetcher = AsyncMock()
        fake_fetcher.fetch_articles = AsyncMock(
            return_value=ChannelTalkFetchedArticlesResult(
                bundles=(article_bundle,),
                fetched_count=1,
                article_ids=("article-1",),
                next_checkpoint_state=ChannelTalkDocumentArticleState.UNPUBLISHED,
                next_checkpoint_cursor="cursor-2",
            )
        )
        application = ConnectorFullSyncApplication(
            port=ChannelTalkArticleFullSyncAdapter(
                fetcher=fake_fetcher,
                language="ko",
                repository_factory=lambda: fake_repository,
            ),
        )

        result = await application.run_full_sync(
            execution=ChannelTalkArticleFullSyncExecutionRequest(
                tenant_id="channel-123",
                channel_connection=_connection(),
                document_connection=_document_connection(),
            ),
            sync_window=_window(),
        )

        self.assertIsInstance(result, ChannelTalkArticleFullSyncExecutionResult)
        self.assertIsInstance(
            result.fetched,
            ChannelTalkArticleFullSyncFetchResult,
        )
        self.assertIsInstance(
            result.transformed,
            ChannelTalkArticleFullSyncTransformResult,
        )
        self.assertIsInstance(
            result.summary,
            ChannelTalkArticleFullSyncSummaryResult,
        )
        self.assertIsInstance(
            result.persisted,
            ChannelTalkArticleFullSyncPersistResult,
        )
        self.assertEqual(result.connector, ConnectorKey.CHANNEL_TALK)
        self.assertEqual(result.target, CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET)
        self.assertEqual(result.channel_id, "channel-123")
        self.assertEqual(result.space_id, "space-123")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(result.document_count, 1)
        self.assertEqual(result.fetched.fetched_count, 1)
        self.assertEqual(result.fetched.fetched_article_ids, ("article-1",))
        self.assertEqual(result.fetched.bundles, (article_bundle,))
        self.assertEqual(
            result.fetched.next_checkpoint.state,
            ChannelTalkDocumentArticleState.UNPUBLISHED,
        )
        self.assertEqual(result.fetched.next_checkpoint.next_cursor, "cursor-2")
        fake_fetcher.fetch_articles.assert_awaited_once()
        fetch_call = fake_fetcher.fetch_articles.await_args.kwargs
        self.assertEqual(fetch_call["connection"].access_key, "documents-access-key")
        self.assertEqual(
            fetch_call["connection"].access_secret, "documents-access-secret"
        )
        self.assertEqual(fetch_call["language"], "ko")
        self.assertEqual(
            fetch_call["states"], DEFAULT_ARTICLE_FULL_SYNC_STATES
        )
        self.assertEqual(fetch_call["sync_window"], _window())
        self.assertEqual(result.summary.document_count, 1)
        self.assertEqual(result.persisted.persisted_count, 1)
        self.assertEqual(
            fake_repository.deleted_prefixes,
            (
                [
                    "channel_talk:document_article:"
                    "channel-123:space-123:ko:article-1:chunk:"
                ]
            ),
        )
        self.assertEqual(len(fake_repository.added_documents), 1)
        stored_document = fake_repository.added_documents[0]
        self.assertNotIn("Document State:", stored_document.page_content)
        self.assertNotIn("State Meaning:", stored_document.page_content)
        self.assertIn("Published article", stored_document.page_content)
        self.assertNotIn("article_state", stored_document.metadata)
        self.assertNotIn("state", stored_document.metadata)
        self.assertEqual(
            stored_document.metadata["url"],
            "https://guide.catchup.im/ko/articles/published-article-23bb29b0",
        )
        document_article_core = stored_document.metadata["document_article_core"]
        self.assertEqual(
            document_article_core["article"]["state"],
            "published",
        )
        self.assertEqual(
            document_article_core["space"]["space_id"],
            "space-123",
        )
        self.assertEqual(
            document_article_core["publication"]["published_revision_id"],
            "published-revision-1",
        )
        self.assertNotIn(
            "summary",
            document_article_core["article"],
        )

    def test_document_article_execution_requires_aligned_connections(self) -> None:
        with self.assertRaisesRegex(ValidationError, "document_connection.channel_id"):
            ChannelTalkArticleFullSyncExecutionRequest(
                tenant_id="channel-123",
                channel_connection=_connection(),
                document_connection=_document_connection().model_copy(
                    update={"channel_id": "other-channel"},
                ),
            )


class ConnectorFullSyncApplicationTests(IsolatedAsyncioTestCase):
    def _build_application(
        self,
        *,
        summarizer=None,
        enable_summarization: bool = True,
        fetched_user_chats: ChannelTalkFetchedUserChatsResult | None = None,
    ) -> tuple[ConnectorFullSyncApplication, _FakeRepository]:
        fake_fetcher = AsyncMock()
        fake_fetcher.fetch_user_chats = AsyncMock(
            return_value=fetched_user_chats
            or ChannelTalkFetchedUserChatsResult(bundles=(_fetched_bundle(),))
        )
        fake_fetcher.fetch_managers_by_id = AsyncMock(return_value=_managers_by_id())
        fake_repository = _FakeRepository()
        application = ConnectorFullSyncApplication(
            port=ChannelTalkUserChatFullSyncAdapter(
                fetcher=fake_fetcher,
                connection_loader=lambda channel_id: _connection(),
                repository_factory=lambda: fake_repository,
                enable_summarization=enable_summarization,
                summarizer=summarizer,
            )
        )
        return application, fake_repository

    async def test_application_runs_fetch_transform_summarize_persist_flow_with_explicit_types(
        self,
    ) -> None:
        fake_summarizer = _FakeSummarizer()
        application, fake_repository = self._build_application(
            summarizer=fake_summarizer,
        )
        sync_window = FullSyncWindow(
            window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
            window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
        )

        result = await application.run_full_sync(
            execution=ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id="channel-123",
            ),
            sync_window=sync_window,
        )

        self.assertIsInstance(result, ChannelTalkUserChatFullSyncExecutionResult)
        self.assertIsInstance(result.fetched, ChannelTalkUserChatFullSyncFetchResult)
        self.assertIsInstance(
            result.transformed,
            ChannelTalkUserChatFullSyncTransformResult,
        )
        self.assertIsInstance(result.summary, ChannelTalkUserChatFullSyncSummaryResult)
        self.assertIsInstance(result.persisted, ChannelTalkUserChatFullSyncPersistResult)
        self.assertEqual(result.connector, ConnectorKey.CHANNEL_TALK)
        self.assertEqual(result.channel_id, "channel-123")
        self.assertNotIn("stage", result.model_dump())
        self.assertNotIn("stage", result.fetched.model_dump())
        self.assertEqual(
            result.fetched.states,
            (
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
                ChannelTalkUserChatState.SNOOZED,
            ),
        )
        self.assertEqual(result.fetched.states[0], ChannelTalkUserChatState.OPENED)
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(result.document_count, 1)
        self.assertIn("fetched_record_ids", result.fetched.model_dump())
        self.assertNotIn("fetched_user_chat_ids", result.fetched.model_dump())
        self.assertTrue(result.summary.summary_applied)
        self.assertEqual(result.summary.included_message_count, 7)
        self.assertEqual(result.summary.excluded_message_count, 0)
        self.assertEqual(result.persisted.persisted_count, 1)
        self.assertEqual(fake_repository.deleted_ids, [])
        self.assertEqual(len(fake_repository.added_documents), 1)
        stored_document = fake_repository.added_documents[0]
        original_contextual_content = stored_document.metadata["contextual_content"]
        self.assertEqual(stored_document.page_content, "summarized support intent")
        self.assertNotEqual(
            stored_document.page_content,
            original_contextual_content,
        )
        self.assertIn("VIP renewal help", original_contextual_content)
        self.assertIn(
            "User: Customer Kim / kim@example.com", original_contextual_content
        )
        self.assertIn("Assignee: Agent Lee", original_contextual_content)
        self.assertIn("Managers: Agent Lee, Agent Park", original_contextual_content)
        self.assertIn("Tags: VIP", original_contextual_content)
        self.assertIn("Conversation:", original_contextual_content)
        self.assertIn("Agent Lee: Hello from support", original_contextual_content)
        self.assertIn("[내부대화] Agent Lee: private note", original_contextual_content)
        self.assertIn(
            "[입력폼] Customer: Email: kim@example.com", original_contextual_content
        )
        self.assertIn(
            "[파일] Agent Park: guide.pdf (application/pdf)",
            original_contextual_content,
        )
        self.assertIn(
            "[버튼] Agent Lee: Choose an action | 버튼: Open (https://example.com)",
            original_contextual_content,
        )
        self.assertIn("[시스템] System: assign", original_contextual_content)
        self.assertIn(
            "Agent Lee: Read the docs | Support Guide | https://example.com/guide | Troubleshooting steps",
            original_contextual_content,
        )
        self.assertNotIn("Channel Talk UserChat", original_contextual_content)
        self.assertNotIn("chat-123", original_contextual_content)
        self.assertNotIn("Included Messages", original_contextual_content)
        self.assertNotIn("base", stored_document.metadata)
        self.assertNotIn("channel_id", stored_document.metadata)
        self.assertEqual(
            stored_document.metadata["url"],
            "https://desk.channel.io/#/channels/channel-123/user_chats/chat-123",
        )
        self.assertEqual(
            stored_document.metadata["user_chat_core"]["chat"]["description"],
            "VIP renewal help",
        )
        self.assertEqual(
            stored_document.metadata["user_chat_core"]["assignment"]["assignee_name"],
            "Agent Lee",
        )
        self.assertEqual(
            stored_document.metadata["user_chat_core"]["assignment"]["manager_names"],
            ["Agent Lee", "Agent Park"],
        )
        self.assertEqual(result.fetched.sync_window, sync_window)
        self.assertEqual(
            result.transformed.documents[
                0
            ].logical_metadata.user_chat_core.messages.excluded_message_count,
            0,
        )

    async def test_summarize_uses_channel_talk_user_chat_source_type(self) -> None:
        fake_summarizer = _FakeSummarizer()
        application, fake_repository = self._build_application(
            summarizer=fake_summarizer,
        )
        audit_context = SyncAuditContext(
            connector=SyncConnector.CHANNEL_TALK,
            scope_id="channel-123",
            target_id="user_chat",
            job_id="job-123",
            task_id="event-123",
        )

        result = await application.run_full_sync(
            execution=ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id="channel-123",
                audit_context=audit_context,
            ),
            sync_window=_window(),
        )

        stored_document = fake_repository.added_documents[0]
        self.assertEqual(len(fake_summarizer.requests), 1)
        self.assertEqual(
            fake_summarizer.requests[0].content,
            result.transformed.documents[0].contextual_content,
        )
        self.assertEqual(
            fake_summarizer.requests[0].content,
            stored_document.metadata["contextual_content"],
        )
        self.assertEqual(
            fake_summarizer.requests[0].source_type,
            "channel_talk_user_chat",
        )
        self.assertEqual(
            fake_summarizer.context,
            "entity_type=user_chat,channel_id=channel-123,doc_count=1",
        )
        self.assertEqual(fake_summarizer.audit_context, audit_context)

    async def test_summarize_disabled_keeps_contextual_content_as_page_content(
        self,
    ) -> None:
        fake_summarizer = _FakeSummarizer()
        application, fake_repository = self._build_application(
            enable_summarization=False,
            summarizer=fake_summarizer,
        )

        result = await application.run_full_sync(
            execution=ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id="channel-123",
            ),
            sync_window=_window(),
        )

        stored_document = fake_repository.added_documents[0]
        self.assertFalse(result.summary.summary_applied)
        self.assertEqual(fake_summarizer.requests, [])
        self.assertEqual(
            stored_document.page_content,
            stored_document.metadata["contextual_content"],
        )

    async def test_application_rejects_checkpoint_window_mismatch_during_fetch(
        self,
    ) -> None:
        application, _ = self._build_application(enable_summarization=False)
        execution = ChannelTalkUserChatFullSyncExecutionRequest(
            tenant_id="channel-123",
            checkpoint=ChannelTalkUserChatFullSyncCheckpoint(
                tenant_id="channel-123",
                state=ChannelTalkUserChatState.OPENED,
                window=_window(),
                next_cursor="cursor-1",
            ),
        )
        mismatched_window = FullSyncWindow(
            window_start=datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
            window_end=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        )

        with self.assertRaisesRegex(
            ValueError,
            "checkpoint.window must match sync_window",
        ):
            await application.run_full_sync(
                execution=execution,
                sync_window=mismatched_window,
            )

    async def test_application_resolves_fetch_states_inside_adapter(self) -> None:
        application, _ = self._build_application(enable_summarization=False)

        result = await application.run_full_sync(
            execution=ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id="channel-123",
                checkpoint=ChannelTalkUserChatFullSyncCheckpoint(
                    tenant_id="channel-123",
                    state=ChannelTalkUserChatState.CLOSED,
                    window=_window(),
                    next_cursor="cursor-1",
                ),
            ),
            sync_window=_window(),
        )

        self.assertEqual(
            result.fetched.states,
            (
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
                ChannelTalkUserChatState.SNOOZED,
            ),
        )
        self.assertIsNone(result.fetched.next_checkpoint)

    async def test_application_surfaces_fetcher_next_checkpoint(self) -> None:
        application, _ = self._build_application(
            enable_summarization=False,
            fetched_user_chats=ChannelTalkFetchedUserChatsResult(
                next_checkpoint_state=ChannelTalkUserChatState.CLOSED,
                next_checkpoint_cursor="closed-page-2",
            ),
        )

        result = await application.run_full_sync(
            execution=ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id="channel-123",
            ),
            sync_window=_window(),
        )

        self.assertIsNotNone(result.fetched.next_checkpoint)
        self.assertEqual(
            result.fetched.next_checkpoint.state, ChannelTalkUserChatState.CLOSED
        )
        self.assertEqual(result.fetched.next_checkpoint.next_cursor, "closed-page-2")

    async def test_fetch_loads_sync_connection_in_threadpool(self) -> None:
        fake_fetcher = AsyncMock()
        fake_fetcher.fetch_managers_by_id = AsyncMock(return_value={})
        fake_fetcher.fetch_user_chats = AsyncMock(
            return_value=ChannelTalkFetchedUserChatsResult()
        )
        adapter = ChannelTalkUserChatFullSyncAdapter(
            fetcher=fake_fetcher,
            connection_loader=lambda channel_id: _connection(),
            enable_summarization=False,
        )

        async def run_sync(operation, *args, **kwargs):
            return operation(*args, **kwargs)

        with patch(
            "catchup.connector_core.adapters.channel_talk.user_chat_full_sync.run_in_threadpool",
            AsyncMock(side_effect=run_sync),
        ) as run_in_threadpool:
            await adapter.fetch(
                execution=ChannelTalkUserChatFullSyncExecutionRequest(
                    tenant_id="channel-123",
                ),
                sync_window=_window(),
            )

        run_in_threadpool.assert_awaited_once()
        self.assertEqual(run_in_threadpool.await_args.args[1], "channel-123")
