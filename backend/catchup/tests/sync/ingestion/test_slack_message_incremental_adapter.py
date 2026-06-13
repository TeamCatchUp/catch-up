from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from langchain_core.documents import Document

from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.sync.ingestion.adapters.slack import SlackMessageIncrementalSyncAdapter
from catchup.sync.ingestion.adapters.slack import (
    SlackMessageIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.slack import SlackMessageTransformResult
from catchup.sync.ingestion.schemas import SyncWindow


def _window() -> SyncWindow:
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _make_adapter(
    *,
    client=None,
    repository=None,
) -> tuple[SlackMessageIncrementalSyncAdapter, SimpleNamespace]:
    repo = repository or SimpleNamespace(
        delete_documents=AsyncMock(),
        upsert_documents=AsyncMock(return_value=[]),
    )
    adapter = SlackMessageIncrementalSyncAdapter(
        team_id="T123",
        client=client or SimpleNamespace(),
        repository=repo,
    )
    adapter._load_channel_context_db = lambda _channel_id: "general"
    return adapter, repo


class SlackMessageIncrementalSyncAdapterTests(IsolatedAsyncioTestCase):
    async def test_updated_event_upserts_transformed_exact_message(self) -> None:
        document = Document(
            id="slack:message:T123:C123:1711.0001",
            page_content="parent message with refreshed replies",
            metadata={"channel_id": "C123"},
        )
        client = SimpleNamespace(
            get_message=AsyncMock(
                return_value={
                    "ts": "1711.0001",
                    "text": "parent message with enough text for ingestion",
                    "reply_count": 0,
                }
            )
        )
        adapter, repository = _make_adapter(client=client)
        adapter._transform_messages = AsyncMock(
            return_value=([document], [document.id], 0, "1711.0001")
        )
        execution = SlackMessageIncrementalSyncExecutionRequest(
            tenant_id="T123",
            channel_id="C123",
            record_id="1711.0001",
            event_kind="updated",
        )

        fetched = await adapter.fetch(execution=execution, sync_window=_window())
        transformed = await adapter.transform(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        client.get_message.assert_awaited_once_with(channel="C123", ts="1711.0001")
        adapter._transform_messages.assert_awaited_once()
        repository.upsert_documents.assert_awaited_once()
        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[0], [document])
        self.assertEqual(upsert_call.args[1], [document.id])
        self.assertEqual(persisted.persisted_count, 1)
        self.assertEqual(transformed.latest_synced_ts, "1711.0001")

    async def test_updated_event_deletes_when_exact_fetch_misses(self) -> None:
        client = SimpleNamespace(get_message=AsyncMock(return_value=None))
        adapter, repository = _make_adapter(client=client)
        execution = SlackMessageIncrementalSyncExecutionRequest(
            tenant_id="T123",
            channel_id="C123",
            record_id="1711.0001",
            event_kind="updated",
        )

        fetched = await adapter.fetch(execution=execution, sync_window=_window())
        transformed = await adapter.transform(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        repository.upsert_documents.assert_not_awaited()
        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )
        self.assertEqual(persisted.deleted_count, 1)

    async def test_updated_event_rejects_missing_record_id(self) -> None:
        adapter, repository = _make_adapter()

        with self.assertRaisesRegex(ValueError, "record_id"):
            SlackMessageIncrementalSyncExecutionRequest(
                tenant_id="T123",
                channel_id="C123",
                record_id=" ",
                event_kind="updated",
            )

        repository.upsert_documents.assert_not_awaited()
        repository.delete_documents.assert_not_awaited()

    async def test_updated_event_deletes_for_skippable_fetch_errors(self) -> None:
        client = SimpleNamespace(
            get_message=AsyncMock(
                side_effect=SlackConnectorApiError(
                    "not in channel",
                    metadata={"error": "not_in_channel"},
                )
            )
        )
        adapter, repository = _make_adapter(client=client)
        execution = SlackMessageIncrementalSyncExecutionRequest(
            tenant_id="T123",
            channel_id="C123",
            record_id="1711.0001",
            event_kind="updated",
        )

        fetched = await adapter.fetch(execution=execution, sync_window=_window())
        transformed = await adapter.transform(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        repository.upsert_documents.assert_not_awaited()
        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )
        self.assertEqual(persisted.deleted_count, 1)

    async def test_deleted_event_deletes_document_without_fetching_message(self) -> None:
        client = SimpleNamespace(get_message=AsyncMock())
        adapter, repository = _make_adapter(client=client)
        execution = SlackMessageIncrementalSyncExecutionRequest(
            tenant_id="T123",
            channel_id="C123",
            record_id="1711.0001",
            event_kind="deleted",
        )

        fetched = await adapter.fetch(execution=execution, sync_window=_window())
        transformed = await adapter.transform(
            execution=execution,
            sync_window=_window(),
            fetched=fetched,
        )
        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        client.get_message.assert_not_awaited()
        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )
        self.assertEqual(persisted.deleted_count, 1)

    async def test_empty_transform_result_is_skipped(self) -> None:
        adapter, repository = _make_adapter()
        execution = SlackMessageIncrementalSyncExecutionRequest(
            tenant_id="T123",
            channel_id="C123",
            record_id="1711.0001",
            event_kind="updated",
        )
        transformed = SlackMessageTransformResult(channel_name="general")

        summary = await adapter.summarize(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
        )
        persisted = await adapter.persist(
            execution=execution,
            sync_window=_window(),
            transformed=transformed,
            summary=summary,
        )

        repository.upsert_documents.assert_not_awaited()
        repository.delete_documents.assert_not_awaited()
        self.assertTrue(persisted.skipped)
