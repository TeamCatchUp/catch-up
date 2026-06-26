from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catchup.sync.backfill.channel_talk_user_chat_v2 import _embedding_to_list
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_channel_talk_user_chat_v1_target_query,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_channel_talk_user_chat_v1_target_seed_query,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_fetch_seeded_seed_chunk_query,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_upsert_seed_rows_statement,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_backfill import (
    ChannelTalkUserChatV2BackfillAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_document_builder import (
    ChannelTalkUserChatV2DocumentBuilder,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _connection
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _fetched_bundle
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _managers_by_id
from catchup.tests.sync.ingestion.test_channel_talk_full_sync import _window


def _seed() -> ChannelTalkUserChatV2BackfillSeed:
    return ChannelTalkUserChatV2BackfillSeed(
        langchain_id="channel_talk:user_chat:channel-123:chat-123",
        record_id="chat-123",
        content="v1 summarized content",
        embedding=[0.1, 0.2, 0.3],
    )


class _FakeChannelTalkAuthorResolver:
    def __init__(self, resolved_id: str | None = "42") -> None:
        self.resolved_id = resolved_id
        self.manager_ids: list[str | None] = []

    def resolve_catchup_user_id(self, db, manager_id):
        _ = db
        self.manager_ids.append(manager_id)
        return self.resolved_id


def _v2_document_builder(
    resolver: _FakeChannelTalkAuthorResolver | None = None,
) -> ChannelTalkUserChatV2DocumentBuilder:
    return ChannelTalkUserChatV2DocumentBuilder(
        author_resolver=resolver or _FakeChannelTalkAuthorResolver(),
        session_factory=lambda: nullcontext(object()),
    )


def test_channel_talk_user_chat_backfill_queries_follow_v1_seed_pattern() -> None:
    target_query = str(build_channel_talk_user_chat_v1_target_query())
    target_seed_query = str(build_channel_talk_user_chat_v1_target_seed_query())
    seed_query = str(build_fetch_seeded_seed_chunk_query())
    upsert_statement = str(build_upsert_seed_rows_statement())

    assert "e.cmetadata ->> 'source' = 'channel_talk'" in target_query
    assert "e.cmetadata ->> 'entity_type' = 'user_chat'" in target_query
    assert "LEFT JOIN knowledge_store v2" in target_query
    assert "needs_backfill" in target_query
    assert "SELECT\n            grouped.scope_id," in target_query
    assert "grouped.expected_count" in target_query
    assert "state.next_retry_at IS NULL" in target_query
    assert "state.state = 'processing'" in target_query
    assert "state.processing_started_at" in target_query
    assert "v2.internal_author_id IS NULL" in target_query
    assert "#>> '{channel_talk_user_chat,assignment,assignee_id}'" in target_query
    assert "v2.internal_author_id IS NULL" in target_seed_query
    assert "(record_id, langchain_id) >" in target_seed_query
    assert "CAST(:after_record_id AS text)" in target_seed_query
    assert "CAST(:after_langchain_id AS text)" in target_seed_query
    assert "ORDER BY record_id, langchain_id" in target_seed_query
    assert "LIMIT :limit" in target_seed_query
    assert "OFFSET" not in target_seed_query
    assert "scope_id = :scope_id" in seed_query
    assert "target_id = :target_id" in seed_query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in seed_query
    assert "INSERT INTO knowledge_store" in upsert_statement
    assert "'channel_talk'" in upsert_statement
    assert "'user_chat'" in upsert_statement
    assert "'channel'" in upsert_statement
    assert "metadata = '{}'::json" not in upsert_statement
    assert "title = ''" not in upsert_statement
    assert "body = ''" not in upsert_statement
    assert "data = '{}'::jsonb" not in upsert_statement
    assert "url = ''" not in upsert_statement


def test_channel_talk_user_chat_v2_embedding_to_list_treats_null_as_empty() -> None:
    assert _embedding_to_list(None) == []


@pytest.mark.asyncio
async def test_backfill_adapter_hydrates_user_chat_and_reuses_v1_seed_values() -> None:
    seed = _seed()
    fetcher = SimpleNamespace(
        fetch_managers_by_id=AsyncMock(return_value=_managers_by_id()),
        fetch_user_chat_bundle_by_id=AsyncMock(return_value=_fetched_bundle()),
    )
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
    )
    v2_knowledge_repository = SimpleNamespace(
        find_missing_metadata_namespace_ids=AsyncMock(return_value=()),
    )
    author_resolver = _FakeChannelTalkAuthorResolver()
    adapter = ChannelTalkUserChatV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
        v2_document_builder=_v2_document_builder(author_resolver),
    )
    adapter._load_connection = AsyncMock(
        return_value=ChannelTalkUserChatFullSyncConnection.from_credentials_record(
            _connection()
        )
    )

    result = await run_sync_ingestion(
        port=adapter,
        execution=ChannelTalkUserChatV2BackfillExecutionRequest(
            tenant_id="channel-123",
            seeds=(seed,),
        ),
        sync_window=_window(),
    )

    assert result.persisted_count == 1
    assert result.v2_failed_count == 0
    assert result.metadata["failed_ids"] == []
    fetcher.fetch_user_chat_bundle_by_id.assert_awaited_once()
    vector_store.upsert_documents.assert_awaited_once()
    upsert_args = vector_store.upsert_documents.await_args
    document = upsert_args.args[0][0]
    assert document.id == seed.langchain_id
    assert document.page_content == seed.content
    assert document.metadata["body"]
    assert author_resolver.manager_ids == ["manager-1"]
    assert document.metadata["internal_author_id"] == "42"
    assert upsert_args.kwargs["ids"] == [seed.langchain_id]
    assert upsert_args.kwargs["embeddings"] == [seed.embedding]
    v2_knowledge_repository.find_missing_metadata_namespace_ids.assert_awaited_once_with(
        [seed.langchain_id],
        namespace="channel_talk_user_chat",
    )


@pytest.mark.asyncio
async def test_backfill_adapter_treats_missing_user_chat_metadata_as_failed() -> None:
    seed = _seed()
    fetcher = SimpleNamespace(
        fetch_managers_by_id=AsyncMock(return_value=_managers_by_id()),
        fetch_user_chat_bundle_by_id=AsyncMock(return_value=_fetched_bundle()),
    )
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
    )
    v2_knowledge_repository = SimpleNamespace(
        find_missing_metadata_namespace_ids=AsyncMock(
            return_value=(seed.langchain_id,)
        ),
    )
    adapter = ChannelTalkUserChatV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
        v2_document_builder=_v2_document_builder(),
    )
    adapter._load_connection = AsyncMock(
        return_value=ChannelTalkUserChatFullSyncConnection.from_credentials_record(
            _connection()
        )
    )

    result = await run_sync_ingestion(
        port=adapter,
        execution=ChannelTalkUserChatV2BackfillExecutionRequest(
            tenant_id="channel-123",
            seeds=(seed,),
        ),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.v2_failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]


@pytest.mark.asyncio
async def test_backfill_adapter_reports_hydrate_failure_as_v2_failed_id() -> None:
    seed = _seed()
    fetcher = SimpleNamespace(
        fetch_managers_by_id=AsyncMock(return_value={}),
        fetch_user_chat_bundle_by_id=AsyncMock(side_effect=RuntimeError("gone")),
    )
    vector_store = SimpleNamespace(upsert_documents=AsyncMock())
    adapter = ChannelTalkUserChatV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
        v2_document_builder=_v2_document_builder(),
    )
    adapter._load_connection = AsyncMock(
        return_value=ChannelTalkUserChatFullSyncConnection.from_credentials_record(
            _connection()
        )
    )

    result = await run_sync_ingestion(
        port=adapter,
        execution=ChannelTalkUserChatV2BackfillExecutionRequest(
            tenant_id="channel-123",
            seeds=(seed,),
        ),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.v2_failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    vector_store.upsert_documents.assert_not_awaited()
