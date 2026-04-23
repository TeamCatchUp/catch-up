from __future__ import annotations

from datetime import datetime
from datetime import timezone
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase
from unittest.mock import AsyncMock

from pydantic import ValidationError

from catchup.connector_core.application.full_sync import ConnectorFullSyncApplication
from catchup.connector_core.descriptors.channel_talk import CHANNEL_TALK_DESCRIPTOR
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.full_sync_fetcher import ChannelTalkFetchedUserChat
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkManagerMetadata
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatListItem
from catchup.connectors.channel_talk.schemas import ChannelTalkUserChatMessage
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "connector_core"
    / "adapters"
    / "channel_talk"
    / "full_sync_adapter.py"
)
_SPEC = spec_from_file_location(
    "catchup.tests.connector_core._channel_talk_full_sync_adapter",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

ChannelTalkFullSyncAdapter = _MODULE.ChannelTalkFullSyncAdapter
ChannelTalkFullSyncExecutionRequest = _MODULE.ChannelTalkFullSyncExecutionRequest
ChannelTalkFullSyncExecutionResult = _MODULE.ChannelTalkFullSyncExecutionResult
ChannelTalkFullSyncFetchResult = _MODULE.ChannelTalkFullSyncFetchResult
ChannelTalkFullSyncTransformResult = _MODULE.ChannelTalkFullSyncTransformResult
ChannelTalkFullSyncSummaryResult = _MODULE.ChannelTalkFullSyncSummaryResult
ChannelTalkFullSyncPersistResult = _MODULE.ChannelTalkFullSyncPersistResult
ChannelTalkFullSyncCheckpoint = _MODULE.ChannelTalkFullSyncCheckpoint
ChannelTalkUserChatState = _MODULE.ChannelTalkUserChatState

ChannelTalkFullSyncCheckpoint.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncFetchResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncTransformResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncSummaryResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncPersistResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncExecutionRequest.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncExecutionResult.model_rebuild(_types_namespace=_MODULE.__dict__)


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
            "userChatId": "chat-123",
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
            "userChatId": "chat-123",
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
            "userChatId": "chat-123",
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
            "userChatId": "chat-123",
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
            "userChatId": "chat-123",
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
            "userChatId": "chat-123",
            "personType": "manager",
            "personId": "manager-1",
            "log": {"action": "assign"},
            "private": True,
            "createdAt": "2026-04-21T09:09:00Z",
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
        self.added_documents = []
        self._initialized = False

    def ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("not initialized")

    async def initialize(self, _ensure_indices) -> None:
        self._initialized = True

    async def delete_documents(self, ids: list[str]) -> None:
        self.deleted_ids = list(ids)

    async def add_documents(self, documents, ids=None):
        self.added_documents = list(documents)
        return list(ids or [])


class ChannelTalkFullSyncContractTests(TestCase):
    def test_execution_request_exposes_explicit_channel_talk_user_chat_contract(
        self,
    ) -> None:
        execution = ChannelTalkFullSyncExecutionRequest(
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
            ChannelTalkFullSyncExecutionRequest(
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
            ChannelTalkFullSyncExecutionRequest(
                tenant_id="channel-123",
                checkpoint=ChannelTalkFullSyncCheckpoint(
                    tenant_id="other-channel",
                    state=ChannelTalkUserChatState.OPENED,
                    window=_window(),
                ),
            )

    def test_checkpoint_remains_target_scoped_without_redundant_stage(self) -> None:
        checkpoint = ChannelTalkFullSyncCheckpoint(
            tenant_id="channel-123",
            state=ChannelTalkUserChatState.OPENED,
            window=_window(),
            next_cursor="cursor-1",
        )

        self.assertEqual(checkpoint.target, "user_chat")
        self.assertNotIn("stage", checkpoint.model_dump())

    def test_descriptor_enables_runtime_full_sync_for_user_chat_contract(self) -> None:
        descriptor = CHANNEL_TALK_DESCRIPTOR

        self.assertTrue(descriptor.runtime.supports_full_sync)
        self.assertEqual(descriptor.runtime.targets[0], "user_chat")


class ConnectorFullSyncApplicationTests(IsolatedAsyncioTestCase):
    def _build_application(
        self,
        *,
        summarizer=None,
        enable_summarization: bool = True,
    ) -> tuple[ConnectorFullSyncApplication, _FakeRepository]:
        fake_fetcher = AsyncMock()
        fake_fetcher.fetch_user_chats = AsyncMock(return_value=(_fetched_bundle(),))
        fake_fetcher.fetch_managers_by_id = AsyncMock(return_value=_managers_by_id())
        fake_repository = _FakeRepository()
        application = ConnectorFullSyncApplication(
            port=ChannelTalkFullSyncAdapter(
                fetcher=fake_fetcher,
                connection_loader=_connection,
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
            execution=ChannelTalkFullSyncExecutionRequest(
                tenant_id="channel-123",
            ),
            sync_window=sync_window,
        )

        self.assertIsInstance(result, ChannelTalkFullSyncExecutionResult)
        self.assertIsInstance(result.fetched, ChannelTalkFullSyncFetchResult)
        self.assertIsInstance(
            result.transformed,
            ChannelTalkFullSyncTransformResult,
        )
        self.assertIsInstance(result.summary, ChannelTalkFullSyncSummaryResult)
        self.assertIsInstance(result.persisted, ChannelTalkFullSyncPersistResult)
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
        self.assertEqual(result.summary.included_message_count, 6)
        self.assertEqual(result.summary.excluded_message_count, 0)
        self.assertEqual(result.persisted.persisted_count, 1)
        self.assertEqual(len(fake_repository.added_documents), 1)
        stored_document = fake_repository.added_documents[0]
        original_contextual_content = stored_document.metadata["contextual_content"]
        self.assertEqual(stored_document.page_content, "summarized support intent")
        self.assertNotEqual(
            stored_document.page_content,
            original_contextual_content,
        )
        self.assertIn("VIP renewal help", original_contextual_content)
        self.assertIn("User: Customer Kim / kim@example.com", original_contextual_content)
        self.assertIn("Assignee: Agent Lee", original_contextual_content)
        self.assertIn("Managers: Agent Lee, Agent Park", original_contextual_content)
        self.assertIn("Tags: VIP", original_contextual_content)
        self.assertIn("Conversation:", original_contextual_content)
        self.assertIn("Agent Lee: Hello from support", original_contextual_content)
        self.assertIn("[내부대화] Agent Lee: private note", original_contextual_content)
        self.assertIn("[입력폼] Customer: Email: kim@example.com", original_contextual_content)
        self.assertIn("[파일] Agent Park: guide.pdf (application/pdf)", original_contextual_content)
        self.assertIn(
            "[버튼] Agent Lee: Choose an action | 버튼: Open (https://example.com)",
            original_contextual_content,
        )
        self.assertIn("[시스템] System: assign", original_contextual_content)
        self.assertNotIn("Channel Talk UserChat", original_contextual_content)
        self.assertNotIn("chat-123", original_contextual_content)
        self.assertNotIn("Included Messages", original_contextual_content)
        self.assertNotIn("base", stored_document.metadata)
        self.assertNotIn("channel_id", stored_document.metadata)
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
            result.transformed.documents[0].logical_metadata.user_chat_core.messages.excluded_message_count,
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
            execution=ChannelTalkFullSyncExecutionRequest(
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
            execution=ChannelTalkFullSyncExecutionRequest(
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

    async def test_application_rejects_checkpoint_window_mismatch_during_fetch(self) -> None:
        application, _ = self._build_application(enable_summarization=False)
        execution = ChannelTalkFullSyncExecutionRequest(
            tenant_id="channel-123",
            checkpoint=ChannelTalkFullSyncCheckpoint(
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
            execution=ChannelTalkFullSyncExecutionRequest(
                tenant_id="channel-123",
                checkpoint=ChannelTalkFullSyncCheckpoint(
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
