from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.sync.common.schemas import TargetSyncResult


def _make_service() -> tuple[SlackIngestionService, SimpleNamespace]:
    repository = SimpleNamespace(
        delete_documents=AsyncMock(),
        upsert_documents=AsyncMock(return_value=[]),
    )

    with patch(
        "catchup.connectors.slack.ingestion_service.SlackApiClientWrapper",
        return_value=SimpleNamespace(),
    ):
        service = SlackIngestionService(
            repository=repository,
            team_id="T123",
            access_token="token",
            enable_summarization=False,
        )

    service._initialized = True
    service.transformer = Mock()
    return service, repository


class SlackIngestionServiceIncrementalSyncTests(IsolatedAsyncioTestCase):
    async def test_incremental_sync_upserts_exact_message_document_for_updates(self) -> None:
        service, repository = _make_service()
        document = Document(
            id="slack:message:T123:C123:1711.0001",
            page_content="parent message with refreshed replies",
            metadata={"channel_id": "C123"},
        )

        with (
            patch.object(service, "_load_channel_context_db", return_value="general"),
            patch.object(
                service,
                "_fetch_message_document",
                AsyncMock(return_value=document),
            ) as fetch_message_document,
            patch.object(service, "_sync_channel_messages", AsyncMock()) as sync_channel_messages,
        ):
            result = await service.incremental_sync(
                channel_id="C123",
                record_id="1711.0001",
                event_kind="updated",
                sync_from="1711.9999",
            )

        fetch_message_document.assert_awaited_once_with(
            channel_id="C123",
            channel_name="general",
            message_id="1711.0001",
        )
        sync_channel_messages.assert_not_awaited()
        repository.upsert_documents.assert_awaited_once()

        upsert_call = repository.upsert_documents.await_args
        self.assertEqual(upsert_call.args[0], [document])
        self.assertEqual(upsert_call.args[1], [document.id])
        self.assertEqual(result, TargetSyncResult(synced_count=1))

    async def test_incremental_sync_removes_document_when_exact_fetch_misses(self) -> None:
        service, repository = _make_service()

        with (
            patch.object(service, "_load_channel_context_db", return_value="general"),
            patch.object(
                service,
                "_fetch_message_document",
                AsyncMock(return_value=None),
            ) as fetch_message_document,
            patch.object(
                service,
                "_sync_channel_messages",
                AsyncMock(),
            ) as sync_channel_messages,
        ):
            result = await service.incremental_sync(
                channel_id="C123",
                record_id="1711.0001",
                event_kind="updated",
                sync_from="1711.9999",
                audit_context=SimpleNamespace(trace_id="audit-1"),
            )

        fetch_message_document.assert_awaited_once_with(
            channel_id="C123",
            channel_name="general",
            message_id="1711.0001",
        )
        sync_channel_messages.assert_not_awaited()
        repository.upsert_documents.assert_not_awaited()
        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )
        self.assertEqual(result, TargetSyncResult(synced_count=1))

    async def test_incremental_sync_rejects_missing_record_id_without_channel_fallback(self) -> None:
        service, repository = _make_service()

        with (
            patch.object(service, "_load_channel_context_db") as load_channel_context,
            patch.object(service, "_fetch_message_document", AsyncMock()) as fetch_message_document,
            patch.object(service, "_sync_channel_messages", AsyncMock()) as sync_channel_messages,
        ):
            with self.assertRaisesRegex(ValueError, "record_id is empty"):
                await service.incremental_sync(
                    channel_id="C123",
                    record_id=" ",
                    event_kind="updated",
                    sync_from="1711.9999",
                )

        load_channel_context.assert_not_called()
        fetch_message_document.assert_not_awaited()
        sync_channel_messages.assert_not_awaited()
        repository.upsert_documents.assert_not_awaited()

    async def test_incremental_sync_removes_document_for_skippable_exact_refresh_errors(self) -> None:
        service, repository = _make_service()

        with (
            patch.object(service, "_load_channel_context_db", return_value="general"),
            patch.object(
                service,
                "_fetch_message_document",
                AsyncMock(
                    side_effect=SlackConnectorApiError(
                        "not in channel",
                        metadata={"error": "not_in_channel"},
                    )
                ),
            ) as fetch_message_document,
            patch.object(service, "_sync_channel_messages", AsyncMock()) as sync_channel_messages,
        ):
            result = await service.incremental_sync(
                channel_id="C123",
                record_id="1711.0001",
                event_kind="updated",
                sync_from="1711.9999",
            )

        fetch_message_document.assert_awaited_once_with(
            channel_id="C123",
            channel_name="general",
            message_id="1711.0001",
        )
        repository.upsert_documents.assert_not_awaited()
        sync_channel_messages.assert_not_awaited()
        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )
        self.assertEqual(result, TargetSyncResult(synced_count=1))

    async def test_incremental_sync_deletes_document_for_deleted_events(self) -> None:
        service, repository = _make_service()

        with (
            patch.object(service, "_fetch_message_document", AsyncMock()) as fetch_message_document,
            patch.object(service, "_sync_channel_messages", AsyncMock()) as sync_channel_messages,
        ):
            result = await service.incremental_sync(
                channel_id="C123",
                record_id="1711.0001",
                event_kind="deleted",
                sync_from="1711.9999",
            )

        repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0001"]
        )
        fetch_message_document.assert_not_awaited()
        sync_channel_messages.assert_not_awaited()
        self.assertEqual(result, TargetSyncResult(synced_count=1))
