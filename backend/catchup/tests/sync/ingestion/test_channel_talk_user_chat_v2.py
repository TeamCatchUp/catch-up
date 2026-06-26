from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from catchup.sync.ingestion.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncIngestionAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkFetchedUserChatsResult,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_document_builder import (
    ChannelTalkUserChatV2DocumentBuilder,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.vector_records import ChannelTalkUserChatV2RecordMapper
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _FakeSummarizer
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _fetched_bundle
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _managers_by_id
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _window


class _DualWriteRepository:
    def __init__(self) -> None:
        self._initialized = False
        self.added_documents = []
        self.deleted_ids = []
        self.stored_documents = []
        self.stored_embeddings = []

    def ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("not initialized")

    async def initialize(self, _ensure_indices) -> None:
        self._initialized = True

    async def add_documents(self, documents, ids=None):
        self.added_documents = list(documents)
        return list(ids or [])

    async def generate_embeddings(self, documents, audit_context=None, context=None):
        _ = audit_context
        _ = context
        return [[0.25] for _document in documents]

    async def delete_documents(self, ids):
        self.deleted_ids = list(ids)

    async def store_with_embeddings(
        self,
        documents,
        embeddings,
        ids,
        audit_context=None,
        context=None,
    ):
        _ = audit_context
        _ = context
        self.stored_documents = list(documents)
        self.stored_embeddings = list(embeddings)
        return list(ids)


class _FakeChannelTalkAuthorResolver:
    def __init__(self, resolved_id: str | None = "42") -> None:
        self.resolved_id = resolved_id
        self.manager_ids: list[str | None] = []

    def resolve_catchup_user_id(self, db, manager_id):
        _ = db
        self.manager_ids.append(manager_id)
        return self.resolved_id


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
        "description",
        "managed",
        "priority",
        "goal_state",
        "customer",
        "assignment",
        "tags",
    }
    assert domain_metadata["description"] == "VIP renewal help"
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
    for removed_field in ("messages", "timing", "metrics", "anchors"):
        assert removed_field not in domain_metadata
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


@pytest.mark.asyncio
async def test_channel_talk_user_chat_full_sync_dual_writes_v2_document() -> None:
    fake_fetcher = AsyncMock()
    fake_fetcher.fetch_user_chats = AsyncMock(
        return_value=ChannelTalkFetchedUserChatsResult(bundles=(_fetched_bundle(),))
    )
    fake_fetcher.fetch_managers_by_id = AsyncMock(return_value=_managers_by_id())
    repository = _DualWriteRepository()
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(
            return_value=["channel_talk:user_chat:channel-123:chat-123"]
        )
    )
    author_resolver = _FakeChannelTalkAuthorResolver()
    v2_document_builder = ChannelTalkUserChatV2DocumentBuilder(
        author_resolver=author_resolver,
        session_factory=lambda: nullcontext(object()),
    )
    adapter = ChannelTalkUserChatFullSyncIngestionAdapter(
        enable_v2_dual_write=True,
        vector_store=vector_store,
        v2_document_builder=v2_document_builder,
    )
    adapter._fetcher = fake_fetcher
    adapter._build_repository = lambda: repository
    adapter._load_connection = AsyncMock(
        return_value=type(
            "_Connection",
            (),
            {
                "channel_id": "channel-123",
                "channel_name": "Support",
                "access_key": "access-key",
                "access_secret": "access-secret",
            },
        )()
    )

    with patch(
        "catchup.sync.ingestion.adapters.channel_talk.user_chat_full_sync.get_summarizer_service",
        return_value=_FakeSummarizer(),
    ):
        result = await run_sync_ingestion(
            port=adapter,
            execution=ChannelTalkUserChatSyncExecutionRequest(
                tenant_id="channel-123",
            ),
            sync_window=_window(),
        )

    assert result.persisted_count == 1
    assert result.v2_failed_count == 0
    assert repository.added_documents == []
    assert repository.deleted_ids == ["channel_talk:user_chat:channel-123:chat-123"]
    assert repository.stored_documents[0].page_content == "summarized support intent"
    vector_store.upsert_documents.assert_awaited_once()
    upsert_kwargs = vector_store.upsert_documents.await_args.kwargs
    v2_document = vector_store.upsert_documents.await_args.args[0][0]
    assert upsert_kwargs["ids"] == ["channel_talk:user_chat:channel-123:chat-123"]
    assert upsert_kwargs["embeddings"] == [[0.25]]
    assert v2_document.page_content == "summarized support intent"
    assert "Hello from support" in v2_document.metadata["body"]
    assert author_resolver.manager_ids == ["manager-1"]
    assert v2_document.metadata["internal_author_id"] == "42"
