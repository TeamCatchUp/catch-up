from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_channel_talk_user_chat_v1_target_query,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_fetch_seeded_seed_chunk_query,
)
from catchup.sync.backfill.channel_talk_user_chat_v2 import (
    build_upsert_seed_rows_statement,
)
from catchup.sync.ingestion.adapters.channel_talk import (
    ChannelTalkUserChatV2BackfillAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk import (
    ChannelTalkUserChatV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk import (
    ChannelTalkUserChatV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_models import (
    ChannelTalkUserChatFullSyncConnection,
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


def test_channel_talk_user_chat_backfill_queries_follow_v1_seed_pattern() -> None:
    target_query = str(build_channel_talk_user_chat_v1_target_query())
    seed_query = str(build_fetch_seeded_seed_chunk_query())
    upsert_statement = str(build_upsert_seed_rows_statement())

    assert "e.cmetadata ->> 'source' = 'channel_talk'" in target_query
    assert "e.cmetadata ->> 'entity_type' = 'user_chat'" in target_query
    assert "LEFT JOIN knowledge_store v2" in target_query
    assert "needs_backfill" in target_query
    assert "scope_id = :scope_id" in seed_query
    assert "target_id = :target_id" in seed_query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in seed_query
    assert "INSERT INTO knowledge_store" in upsert_statement
    assert "'channel_talk'" in upsert_statement
    assert "'user_chat'" in upsert_statement
    assert "'channel'" in upsert_statement


@pytest.mark.asyncio
async def test_backfill_adapter_hydrates_user_chat_and_reuses_v1_seed_values() -> None:
    seed = _seed()
    fetcher = SimpleNamespace(
        fetch_managers_by_id=AsyncMock(return_value=_managers_by_id()),
        fetch_user_chat_bundle_by_id=AsyncMock(return_value=_fetched_bundle()),
    )
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id])
    )
    adapter = ChannelTalkUserChatV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
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
    assert upsert_args.kwargs["ids"] == [seed.langchain_id]
    assert upsert_args.kwargs["embeddings"] == [seed.embedding]


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
