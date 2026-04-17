from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.connectors.slack.ingestion_service import SlackSyncContext
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

    async def test_incremental_sync_falls_back_to_channel_sync_when_exact_fetch_misses(self) -> None:
        service, repository = _make_service()
        fallback_result = TargetSyncResult(synced_count=4, error_count=1)

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
                AsyncMock(return_value=fallback_result),
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
        sync_channel_messages.assert_awaited_once()
        self.assertEqual(
            sync_channel_messages.await_args.kwargs["sync_ctx"],
            SlackSyncContext(
                channel_id="C123",
                channel_name="general",
                sync_from_ts="1711.9999",
                skip_delete=False,
                audit_context=SimpleNamespace(trace_id="audit-1"),
            ),
        )
        repository.upsert_documents.assert_not_awaited()
        self.assertIs(result, fallback_result)

    async def test_incremental_sync_skips_skippable_exact_refresh_errors(self) -> None:
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
        self.assertEqual(result, TargetSyncResult(skipped=True))

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
