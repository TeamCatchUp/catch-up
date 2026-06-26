from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from langchain_core.documents import Document

from catchup.connectors.confluence.client import ConfluenceApiError
from catchup.db.models import SyncConnector
from catchup.sync.incremental.poll.confluence import _collect_deleted_blogpost_changes
from catchup.sync.incremental.poll.confluence import _collect_deleted_page_changes
from catchup.sync.incremental.poll.confluence import (
    _exclude_unrecovered_stale_deleted_keys,
)
from catchup.sync.incremental.poll.confluence import _filter_repeated_deleted_changes
from catchup.sync.incremental.resolve.confluence import build_confluence_record_change
from catchup.sync.ingestion.adapters.confluence import (
    ConfluenceSpaceIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.confluence import ConfluenceSpaceSyncAdapter
from catchup.sync.ingestion.adapters.confluence import ConfluenceSpaceSyncDependencies
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceFetchResult,
)
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow


def _window() -> SyncWindow:
    now = datetime(2026, 5, 15, 8, 30, tzinfo=timezone.utc)
    return SyncWindow(window_start=now, window_end=now)


def _build_adapter(
    *,
    client: object | None = None,
    repository: object | None = None,
) -> ConfluenceSpaceSyncAdapter:
    return ConfluenceSpaceSyncAdapter(
        dependencies=ConfluenceSpaceSyncDependencies(
            cloud_id="cloud-1",
            site_url="https://example.atlassian.net/wiki",
            client=client or SimpleNamespace(),
            repository=repository or SimpleNamespace(),
            transformer=SimpleNamespace(),
        ),
    )


class _FakeConfluenceClient:
    def __init__(self) -> None:
        self.page_calls: list[dict[str, object]] = []
        self.blogpost_calls: list[dict[str, object]] = []
        self.page_batches: dict[str, list[list[dict[str, object]]]] = {}
        self.blogpost_batches: dict[str, list[list[dict[str, object]]]] = {}

    async def iter_pages(self, **kwargs):
        self.page_calls.append(kwargs)
        status = str(kwargs.get("status"))
        for batch in self.page_batches.get(status, []):
            yield batch

    async def iter_blogposts(self, **kwargs):
        self.blogpost_calls.append(kwargs)
        status = str(kwargs.get("status"))
        for batch in self.blogpost_batches.get(status, []):
            yield batch


class _FakeRepository:
    def __init__(self) -> None:
        self.deleted_prefixes: list[str] = []

    async def delete_by_id_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)


def _raw_confluence_page(content_id: str, title: str = "Claimed Page") -> dict[str, object]:
    return {
        "id": content_id,
        "status": "current",
        "title": title,
        "spaceId": "space-1",
        "version": {
            "number": 1,
            "createdAt": "2026-05-15T08:30:00.000Z",
        },
        "body": {
            "storage": {
                "representation": "storage",
                "value": "<p>claimed page</p>",
            }
        },
    }


def _raw_confluence_blogpost(content_id: str, title: str = "Claimed Blog") -> dict[str, object]:
    return {
        "id": content_id,
        "status": "current",
        "title": title,
        "spaceId": "space-1",
        "version": {
            "number": 1,
            "createdAt": "2026-05-15T08:30:00.000Z",
        },
        "body": {
            "storage": {
                "representation": "storage",
                "value": "<p>claimed blogpost</p>",
            }
        },
    }


class ConfluenceIncrementalPollTests(IsolatedAsyncioTestCase):
    async def test_collect_deleted_pages_uses_trashed_status_and_deleted_event(self) -> None:
        client = _FakeConfluenceClient()
        client.page_batches["trashed"] = [
            [
                {
                    "id": "123",
                    "version": {"createdAt": "2020-01-01T00:00:00.000Z"},
                }
            ]
        ]
        observed_at = datetime(2026, 5, 15, 8, 30, tzinfo=timezone.utc)

        changes = await _collect_deleted_page_changes(
            client=client,
            cloud_id="cloud-1",
            space_id="space-1",
            space_key="DOC",
            observed_at=observed_at,
            max_batches=20,
        )

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].record_type, "page")
        self.assertEqual(changes[0].record_id, "123")
        self.assertEqual(changes[0].event_kind, "deleted")
        self.assertEqual(changes[0].last_event_at, observed_at)
        self.assertEqual(client.page_calls[0]["status"], "trashed")

    async def test_collect_deleted_blogposts_caps_trashed_pagination(self) -> None:
        client = _FakeConfluenceClient()
        client.blogpost_batches["trashed"] = [
            [{"id": "10"}],
            [{"id": "11"}],
        ]
        observed_at = datetime(2026, 5, 15, 8, 30, tzinfo=timezone.utc)

        changes = await _collect_deleted_blogpost_changes(
            client=client,
            cloud_id="cloud-1",
            space_id="space-1",
            space_key="DOC",
            observed_at=observed_at,
            max_batches=1,
        )

        self.assertEqual([change.record_id for change in changes], ["10"])
        self.assertEqual(changes[0].record_type, "blogpost")
        self.assertEqual(changes[0].event_kind, "deleted")
        self.assertEqual(client.blogpost_calls[0]["status"], "trashed")


class ConfluenceIncrementalResolveTests(IsolatedAsyncioTestCase):
    async def test_build_confluence_change_preserves_deleted_event_kind(self) -> None:
        event_at = datetime(2026, 5, 15, 8, 30, tzinfo=timezone.utc)

        change = build_confluence_record_change(
            cloud_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="123",
            event_kind="deleted",
            last_event_at=event_at,
        )

        self.assertEqual(change.connector, SyncConnector.CONFLUENCE)
        self.assertEqual(change.event_kind, "deleted")
        self.assertEqual(change.record_key, "confluence:cloud-1:space:DOC:page:123")


class ConfluenceIncrementalDeletedDedupeTests(IsolatedAsyncioTestCase):
    async def test_stale_outbox_deleted_records_are_not_treated_as_processed(self) -> None:
        processed_key = "confluence:cloud-1:space:DOC:page:processed"
        stale_key = "confluence:cloud-1:space:DOC:page:stale"
        recovered_key = "confluence:cloud-1:space:DOC:page:recovered"

        filtered_keys = _exclude_unrecovered_stale_deleted_keys(
            existing_deleted_record_keys={processed_key, stale_key, recovered_key},
            stale_skipped_outbox_rows=[
                (stale_key, 3),
                (recovered_key, 2),
            ],
            published_outbox_rows=[
                (processed_key, 1),
                (recovered_key, 4),
            ],
        )

        self.assertEqual(filtered_keys, {processed_key, recovered_key})

    async def test_filter_repeated_deleted_changes_keeps_new_deletes_and_updates(self) -> None:
        event_at = datetime(2026, 5, 15, 8, 30, tzinfo=timezone.utc)
        update_change = build_confluence_record_change(
            cloud_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="updated",
            event_kind="updated",
            last_event_at=event_at,
        )
        new_delete = build_confluence_record_change(
            cloud_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="new-delete",
            event_kind="deleted",
            last_event_at=event_at,
        )
        repeated_delete = build_confluence_record_change(
            cloud_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="old-delete",
            event_kind="deleted",
            last_event_at=event_at,
        )

        with patch(
            "catchup.sync.incremental.poll.confluence._load_existing_deleted_record_keys_sync",
            return_value={repeated_delete.record_key},
        ):
            filtered = await _filter_repeated_deleted_changes(
                [update_change, new_delete, repeated_delete]
            )

        self.assertEqual(filtered, [update_change, new_delete])


class ConfluenceIncrementalDeleteApplyTests(IsolatedAsyncioTestCase):
    async def test_incremental_sync_deletes_chunks_for_deleted_events(self) -> None:
        repository = _FakeRepository()
        adapter = _build_adapter(repository=repository)
        adapter._load_space_sync_context = AsyncMock(  # noqa: SLF001
            return_value=({"DOC": "space-1"}, {"DOC": "Docs"}, {})
        )
        execution = ConfluenceSpaceIncrementalSyncExecutionRequest(
            tenant_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="123",
            event_kind="deleted",
            since=None,
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

        self.assertEqual(repository.deleted_prefixes, ["confluence:page:123:chunk:"])
        self.assertEqual(persisted.deleted_count, 1)
        self.assertEqual(persisted.error_count, 0)


class ConfluenceIncrementalExactRecordAdapterTests(IsolatedAsyncioTestCase):
    async def test_transform_logs_structured_failure_for_non_retryable_errors(
        self,
    ) -> None:
        adapter = _build_adapter()
        adapter._process_page = AsyncMock(  # noqa: SLF001
            side_effect=ValueError("broken transform")
        )
        execution = ConfluenceSpaceIncrementalSyncExecutionRequest(
            tenant_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="123",
            event_kind="updated",
            since=None,
        )
        fetched = ConfluenceSpaceFetchResult(
            requested_count=1,
            records=(_raw_confluence_page("123"),),
            record_type="page",
            space_key="DOC",
            space_name="Docs",
        )

        with patch(
            "catchup.sync.ingestion.adapters.confluence.space_sync.logger"
        ) as logger:
            transformed = await adapter.transform(
                execution=execution,
                sync_window=_window(),
                fetched=fetched,
            )

        self.assertEqual(transformed.error_count, 1)
        self.assertEqual(transformed.items, ())
        logger.warning.assert_called_once_with(
            "confluence_space_transform_item_failed",
            connector="confluence",
            sync_type="incremental",
            entity_type="page",
            scope_id="cloud-1",
            target_id="DOC",
            content_id="123",
            exception_type="ValueError",
            error="broken transform",
            exc_info=True,
        )

    async def test_fetch_supplementary_logs_structured_non_retryable_failures(
        self,
    ) -> None:
        client = SimpleNamespace(
            get_content_footer_comments=AsyncMock(
                side_effect=ValueError("comments down")
            ),
            get_content_labels=AsyncMock(return_value=[]),
            get_content_inline_comments=AsyncMock(return_value=[]),
        )
        adapter = _build_adapter(client=client)

        with patch(
            "catchup.sync.ingestion.adapters.confluence.space_sync.logger"
        ) as logger:
            footer_comments, inline_comments, labels = await adapter._fetch_supplementary(  # noqa: SLF001
                api_content_type="pages",
                content_id="123",
            )

        self.assertEqual(footer_comments, [])
        self.assertEqual(inline_comments, [])
        self.assertEqual(labels, [])
        logger.warning.assert_called_once_with(
            "confluence_supplementary_fetch_failed",
            connector="confluence",
            scope_id="cloud-1",
            entity_type="page",
            api_content_type="pages",
            content_id="123",
            exception_type="ValueError",
            error="comments down",
        )

    async def test_fetch_supplementary_reraises_retryable_failures(self) -> None:
        client = SimpleNamespace(
            get_content_footer_comments=AsyncMock(
                side_effect=ConfluenceApiError(
                    "retry comments",
                    status_code=503,
                    retry_after=30,
                )
            ),
            get_content_labels=AsyncMock(return_value=[]),
            get_content_inline_comments=AsyncMock(return_value=[]),
        )
        adapter = _build_adapter(client=client)

        with self.assertRaisesRegex(ConfluenceApiError, "retry comments"):
            await adapter._fetch_supplementary(  # noqa: SLF001
                api_content_type="pages",
                content_id="123",
            )

    async def test_resolve_vector_store_logs_structured_initialization_failure(
        self,
    ) -> None:
        document = Document(
            id="confluence:page:123:chunk:0",
            page_content="page",
            metadata={},
        )
        adapter = _build_adapter()
        adapter._enable_v2_dual_write = True  # noqa: SLF001
        adapter._get_vector_store = AsyncMock(  # noqa: SLF001
            side_effect=RuntimeError("pool down")
        )

        with patch(
            "catchup.sync.ingestion.adapters.confluence.space_sync.logger"
        ) as logger:
            vector_store = await adapter._resolve_vector_store_for_write(  # noqa: SLF001
                documents=(document,),
            )

        self.assertIsNone(vector_store)
        logger.warning.assert_called_once_with(
            "confluence_vector_store_resolve_failed",
            connector="confluence",
            scope_id="cloud-1",
            document_count=1,
            exception_type="RuntimeError",
            error="pool down",
            exc_info=True,
        )

    async def test_store_transform_result_deletes_existing_chunks_for_empty_documents(self) -> None:
        repository = SimpleNamespace(
            delete_by_id_prefix=AsyncMock(),
            store_with_embeddings=AsyncMock(),
        )
        adapter = _build_adapter(repository=repository)
        adapter._generate_embeddings = AsyncMock()  # noqa: SLF001

        await adapter._store_transform_result(  # noqa: SLF001
            entity_type="page",
            content_id="123",
            space_key="DOC",
            transform_result=ConfluenceTransformResult(documents=[]),
            audit_context=None,
        )

        repository.delete_by_id_prefix.assert_awaited_once_with(
            "confluence:page:123:chunk:"
        )
        adapter._generate_embeddings.assert_not_awaited()  # noqa: SLF001
        repository.store_with_embeddings.assert_not_awaited()

    async def test_generate_embeddings_uses_text_embedding_for_image_backed_chunks(
        self,
    ) -> None:
        documents = [
            Document(id="doc-1", page_content="text only", metadata={}),
            Document(
                id="doc-2",
                page_content="text with image",
                metadata={"has_images": True},
            ),
        ]
        repository = SimpleNamespace(
            generate_embeddings=AsyncMock(
                return_value=[
                    [0.1, 0.2],
                    [0.3, 0.4],
                ]
            )
        )
        adapter = _build_adapter(repository=repository)

        with patch(
            "catchup.sync.ingestion.adapters.confluence.space_sync.logger"
        ) as logger:
            embeddings = await adapter._generate_embeddings(  # noqa: SLF001
                documents,
                entity_type="page",
                content_id="123",
                space_key="DOC",
                audit_context=None,
            )

        self.assertEqual(embeddings, [[0.1, 0.2], [0.3, 0.4]])
        repository.generate_embeddings.assert_awaited_once_with(
            documents,
            audit_context=None,
            context="entity_type=page,space_key=DOC,doc_count=2,embed_mode=text_only",
        )
        logger.info.assert_called_once_with(
            "confluence_embeddings_generated",
            connector="confluence",
            entity_type="page",
            scope_id="cloud-1",
            target_id="DOC",
            content_id="123",
            document_count=2,
            embed_mode="text_only",
            image_document_count=1,
        )

    async def test_store_transform_result_logs_structured_v2_upsert_failure(
        self,
    ) -> None:
        documents = [
            Document(
                id="confluence:page:123:chunk:0",
                page_content="page",
                metadata={},
            )
        ]
        repository = SimpleNamespace(
            delete_by_id_prefix=AsyncMock(),
            generate_embeddings=AsyncMock(return_value=[[0.1, 0.2]]),
            store_with_embeddings=AsyncMock(),
        )
        vector_store = SimpleNamespace(
            upsert_documents=AsyncMock(side_effect=RuntimeError("v2 down"))
        )
        adapter = _build_adapter(repository=repository)

        with patch(
            "catchup.sync.ingestion.adapters.confluence.space_sync.logger"
        ) as logger:
            failed_ids = await adapter._store_transform_result(  # noqa: SLF001
                entity_type="page",
                content_id="123",
                space_key="DOC",
                transform_result=ConfluenceTransformResult(documents=documents),
                audit_context=None,
                vector_store=vector_store,
                v2_documents=documents,
            )

        self.assertEqual(failed_ids, ("confluence:page:123:chunk:0",))
        logger.warning.assert_called_once_with(
            "confluence_v2_upsert_failed",
            connector="confluence",
            entity_type="page",
            scope_id="cloud-1",
            target_id="DOC",
            content_id="123",
            document_count=1,
            exception_type="RuntimeError",
            error="v2 down",
            exc_info=True,
        )

    async def test_incremental_sync_page_fetches_and_stores_only_claimed_record(self) -> None:
        transform_result = ConfluenceTransformResult(
            documents=[Document(id="doc-page-123", page_content="page")]
        )
        client = SimpleNamespace(
            get_page_by_id=AsyncMock(return_value=_raw_confluence_page("123")),
            get_blogpost_by_id=AsyncMock(),
        )
        adapter = _build_adapter(client=client)
        adapter._space_context = AsyncMock(  # noqa: SLF001
            return_value=("space-1", "Docs", {"author-1": "Author One"})
        )
        adapter._process_page = AsyncMock(return_value=transform_result)  # noqa: SLF001
        adapter._store_transform_result = AsyncMock(return_value=())  # noqa: SLF001
        execution = ConfluenceSpaceIncrementalSyncExecutionRequest(
            tenant_id="cloud-1",
            space_key="DOC",
            record_type="page",
            record_id="123",
            event_kind="updated",
            since=datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc),
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

        self.assertEqual(persisted.persisted_count, 1)
        client.get_page_by_id.assert_awaited_once_with("123", body_format="storage")
        client.get_blogpost_by_id.assert_not_awaited()
        adapter._process_page.assert_awaited_once()  # noqa: SLF001
        adapter._store_transform_result.assert_awaited_once_with(  # noqa: SLF001
            entity_type="page",
            content_id="123",
            space_key="DOC",
            transform_result=transform_result,
            audit_context=None,
            vector_store=None,
            v2_documents=[],
        )

    async def test_incremental_sync_blogpost_fetches_and_stores_only_claimed_record(self) -> None:
        transform_result = ConfluenceTransformResult(
            documents=[Document(id="doc-blogpost-456", page_content="blogpost")]
        )
        client = SimpleNamespace(
            get_page_by_id=AsyncMock(),
            get_blogpost_by_id=AsyncMock(return_value=_raw_confluence_blogpost("456")),
        )
        adapter = _build_adapter(client=client)
        adapter._space_context = AsyncMock(  # noqa: SLF001
            return_value=("space-1", "Docs", {"author-1": "Author One"})
        )
        adapter._process_blogpost = AsyncMock(return_value=transform_result)  # noqa: SLF001
        adapter._store_transform_result = AsyncMock(return_value=())  # noqa: SLF001
        execution = ConfluenceSpaceIncrementalSyncExecutionRequest(
            tenant_id="cloud-1",
            space_key="DOC",
            record_type="blogpost",
            record_id="456",
            event_kind="updated",
            since=datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc),
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

        self.assertEqual(persisted.persisted_count, 1)
        client.get_page_by_id.assert_not_awaited()
        client.get_blogpost_by_id.assert_awaited_once_with(
            "456",
            body_format="storage",
        )
        adapter._process_blogpost.assert_awaited_once()  # noqa: SLF001
        adapter._store_transform_result.assert_awaited_once_with(  # noqa: SLF001
            entity_type="blogpost",
            content_id="456",
            space_key="DOC",
            transform_result=transform_result,
            audit_context=None,
            vector_store=None,
            v2_documents=[],
        )
