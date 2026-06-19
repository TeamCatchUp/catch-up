from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from catchup.sync.backfill.slack_message_v2 import SlackMessageV1Seed
from catchup.sync.backfill.slack_message_v2 import _embedding_to_list
from catchup.sync.backfill.slack_message_v2 import build_fetch_pending_seed_chunk_query
from catchup.sync.backfill.slack_message_v2 import build_slack_message_v1_target_query
from catchup.sync.backfill.slack_message_v2 import (
    build_slack_message_v1_target_seed_query,
)
from catchup.sync.backfill.slack_message_v2 import build_upsert_seed_rows_statement
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillAdapter
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillExecutionRequest
from catchup.sync.ingestion.adapters.slack import SlackMessageV2BackfillSeed
from catchup.sync.ingestion.adapters.slack.message_v2_document_builder import (
    SlackMessageV2DocumentBuilder,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow


def _seed() -> SlackMessageV1Seed:
    return SlackMessageV1Seed(
        langchain_id="slack:message:T123:C123:1712345678.000100",
        record_id="1712345678.000100",
        content="summarized v1 slack message content",
        embedding=[0.0123, -0.0456, 0.0789],
    )


def _window() -> SyncWindow:
    now = datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _execution(seed: SlackMessageV1Seed) -> SlackMessageV2BackfillExecutionRequest:
    return SlackMessageV2BackfillExecutionRequest(
        tenant_id="T123",
        channel_id="C123",
        channel_name="general",
        seeds=(
            SlackMessageV2BackfillSeed(
                langchain_id=seed.langchain_id,
                record_id=seed.record_id,
                content=seed.content,
                embedding=seed.embedding,
            ),
        ),
    )


def test_slack_backfill_target_query_skips_finished_rows_and_stale_content() -> None:
    query = str(build_slack_message_v1_target_query())

    assert "WITH v1_message AS" in query
    assert "e.cmetadata ->> 'source' = 'slack'" in query
    assert "e.cmetadata ->> 'entity_type' = 'message'" in query
    assert "pending_count > 0" in query
    assert "v2.content IS DISTINCT FROM v1_message.content" in query
    assert "COALESCE(v2.metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in query
    assert "state.next_retry_at IS NULL" in query
    assert "state.state = 'processing'" in query
    assert "state.processing_started_at" in query
    assert "SELECT\n            grouped.scope_id" in query
    assert "ORDER BY grouped.scope_id, grouped.target_id" in query


def test_slack_backfill_seed_query_skips_already_hydrated_rows() -> None:
    query = str(build_slack_message_v1_target_seed_query())

    assert "LEFT JOIN knowledge_store v2" in query
    assert "needs_backfill" in query
    assert "COALESCE(v2.metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in query
    assert "v2.content IS DISTINCT FROM v1_message.content" in query


def test_slack_timestamp_cursor_uses_decimal_ts_and_tiebreaker() -> None:
    query = str(build_fetch_pending_seed_chunk_query())

    assert "record_id::numeric(20,6) AS record_ts" in query
    assert "record_ts > CAST(:after_record_ts AS numeric(20,6))" in query
    assert "record_ts = CAST(:after_record_ts AS numeric(20,6))" in query
    assert "langchain_id > COALESCE(:after_langchain_id, '')" in query
    assert "ORDER BY record_ts, langchain_id" in query


def test_slack_message_v2_embedding_to_list_treats_null_as_empty() -> None:
    assert _embedding_to_list(None) == []


def test_slack_backfill_seed_rejects_empty_embedding() -> None:
    with pytest.raises(ValueError, match="embedding must not be empty"):
        SlackMessageV2BackfillSeed(
            langchain_id="slack:message:T123:C123:1712345678.000100",
            record_id="1712345678.000100",
            content="summarized v1 slack message content",
            embedding=[],
        )


@pytest.mark.asyncio
async def test_backfill_adapter_hydrates_message_and_reuses_v1_seed_values() -> None:
    seed = _seed()
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
        find_missing_metadata_namespace_ids=AsyncMock(return_value=()),
    )
    session_factory = Mock()
    session_factory.return_value.__enter__ = Mock(return_value=SimpleNamespace())
    session_factory.return_value.__exit__ = Mock(return_value=False)

    adapter = SlackMessageV2BackfillAdapter(
        team_id="T123",
        client=SimpleNamespace(
            get_message=AsyncMock(
                return_value={
                    "ts": seed.record_id,
                    "text": "Ship Slack message v2 migration safely",
                    "user": "U123",
                    "reply_count": 0,
                }
            )
        ),
        repository=SimpleNamespace(),
        vector_store=vector_store,
        v2_document_builder=SlackMessageV2DocumentBuilder(
            session_factory=session_factory,
        ),
    )
    adapter.message_v2_document_builder.author_resolver.resolve_catchup_user_id = Mock(
        return_value="42"
    )
    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(seed),
        sync_window=_window(),
    )

    vector_store.upsert_documents.assert_awaited_once()
    upsert_call = vector_store.upsert_documents.await_args
    document = upsert_call.args[0][0]

    assert result.persisted_count == 1
    assert result.failed_count == 0
    assert result.metadata["failed_ids"] == []
    assert document.id == seed.langchain_id
    assert document.page_content == seed.content
    assert document.metadata["scope_id"] == "T123"
    assert document.metadata["target_id"] == "C123"
    assert document.metadata["slack_message"]["author"]["catchup_user_id"] == "42"
    assert upsert_call.kwargs["ids"] == [seed.langchain_id]
    assert upsert_call.kwargs["embeddings"] == [seed.embedding]
    vector_store.find_missing_metadata_namespace_ids.assert_awaited_once_with(
        [seed.langchain_id],
        namespace="slack_message",
    )


@pytest.mark.asyncio
async def test_backfill_adapter_treats_missing_slack_metadata_as_failed() -> None:
    seed = _seed()
    vector_store = SimpleNamespace(
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
        find_missing_metadata_namespace_ids=AsyncMock(
            return_value=(seed.langchain_id,)
        ),
    )
    session_factory = Mock()
    session_factory.return_value.__enter__ = Mock(return_value=SimpleNamespace())
    session_factory.return_value.__exit__ = Mock(return_value=False)

    adapter = SlackMessageV2BackfillAdapter(
        team_id="T123",
        client=SimpleNamespace(
            get_message=AsyncMock(
                return_value={
                    "ts": seed.record_id,
                    "text": "Ship Slack message v2 migration safely",
                    "user": "U123",
                    "reply_count": 0,
                }
            )
        ),
        repository=SimpleNamespace(),
        vector_store=vector_store,
        v2_document_builder=SlackMessageV2DocumentBuilder(
            session_factory=session_factory,
        ),
    )

    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(seed),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.failed_count == 1
    assert result.v2_failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]
    assert result.metadata["v2_failed_ids"] == [seed.langchain_id]


def test_slack_seed_upsert_does_not_clear_hydrated_fields_on_conflict() -> None:
    statement = str(build_upsert_seed_rows_statement())

    assert "ON CONFLICT (document_id) DO UPDATE SET" in statement
    assert "metadata = '{}'::json" not in statement
    assert "title = ''" not in statement
    assert "body = ''" not in statement
    assert "data = '{}'::jsonb" not in statement
    assert "url = ''" not in statement


@pytest.mark.asyncio
async def test_backfill_adapter_hydrate_failure_reports_v2_failed_id() -> None:
    seed = _seed()
    adapter = SlackMessageV2BackfillAdapter(
        team_id="T123",
        client=SimpleNamespace(get_message=AsyncMock(return_value=None)),
        repository=SimpleNamespace(),
        vector_store=SimpleNamespace(upsert_documents=AsyncMock()),
    )

    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(seed),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]


@pytest.mark.asyncio
async def test_backfill_adapter_transform_failure_reports_failed_seed_id() -> None:
    seed = _seed()
    adapter = SlackMessageV2BackfillAdapter(
        team_id="T123",
        client=SimpleNamespace(
            get_message=AsyncMock(
                return_value={
                    "ts": seed.record_id,
                    "text": "Ship Slack message v2 migration safely",
                    "user": "U123",
                    "reply_count": 0,
                }
            )
        ),
        repository=SimpleNamespace(),
        vector_store=SimpleNamespace(upsert_documents=AsyncMock()),
    )
    adapter._transform_message_bundles = AsyncMock(
        return_value=([], [], 1, None, (seed.record_id,))
    )

    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(seed),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]
    assert result.metadata["failed_record_ids"] == [seed.record_id]


@pytest.mark.asyncio
async def test_backfill_adapter_mapper_failure_reports_v2_failed_id() -> None:
    seed = _seed()
    session_factory = Mock()
    session_factory.return_value.__enter__ = Mock(return_value=SimpleNamespace())
    session_factory.return_value.__exit__ = Mock(return_value=False)

    adapter = SlackMessageV2BackfillAdapter(
        team_id="T123",
        client=SimpleNamespace(
            get_message=AsyncMock(
                return_value={
                    "ts": seed.record_id,
                    "text": "Ship Slack message v2 migration safely",
                    "user": "U123",
                    "reply_count": 0,
                }
            )
        ),
        repository=SimpleNamespace(),
        vector_store=SimpleNamespace(upsert_documents=AsyncMock()),
        v2_document_builder=SlackMessageV2DocumentBuilder(
            session_factory=session_factory,
        ),
    )
    adapter.message_v2_document_builder.mapper.to_document = Mock(
        side_effect=ValueError("bad message")
    )
    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(seed),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]
