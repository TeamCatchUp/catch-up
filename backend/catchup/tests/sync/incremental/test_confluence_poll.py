from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.incremental.poll.confluence import _collect_deleted_blogpost_changes
from catchup.sync.incremental.poll.confluence import _collect_deleted_page_changes
from catchup.sync.incremental.poll.confluence import (
    _exclude_unrecovered_stale_deleted_keys,
)
from catchup.sync.incremental.poll.confluence import _filter_repeated_deleted_changes
from catchup.sync.incremental.resolve.confluence import build_confluence_record_change
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)
from catchup.sync.ingestion.services.confluence import ConfluenceIngestionService


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
        service = ConfluenceIngestionService(
            cloud_id="cloud-1",
            token_provider=SimpleNamespace(),
            site_url="https://example.atlassian.net/wiki",
            repository=repository,
            embedding_service=SimpleNamespace(),
        )

        result = await service.incremental_sync(
            space_key="DOC",
            record_type="page",
            record_id="123",
            event_kind="deleted",
            since=None,
        )

        self.assertEqual(repository.deleted_prefixes, ["confluence:page:123:chunk:"])
        self.assertEqual(result, {"synced": 1, "errors": 0, "skipped": False})


class ConfluenceIncrementalExactRecordServiceTests(IsolatedAsyncioTestCase):
    def _build_service(self) -> ConfluenceIngestionService:
        return ConfluenceIngestionService(
            cloud_id="cloud-1",
            token_provider=SimpleNamespace(),
            site_url="https://example.atlassian.net/wiki",
            repository=SimpleNamespace(),
            embedding_service=SimpleNamespace(),
        )

    async def test_store_transform_result_deletes_existing_chunks_for_empty_documents(self) -> None:
        repository = SimpleNamespace(
            delete_by_id_prefix=AsyncMock(),
            store_with_embeddings=AsyncMock(),
        )
        service = ConfluenceIngestionService(
            cloud_id="cloud-1",
            token_provider=SimpleNamespace(),
            site_url="https://example.atlassian.net/wiki",
            repository=repository,
            embedding_service=SimpleNamespace(),
        )
        service._generate_embeddings = AsyncMock()

        await service._store_transform_result(
            entity_type="page",
            content_id="123",
            space_key="DOC",
            transform_result=ConfluenceTransformResult(documents=[], embed_inputs=[]),
            audit_context=None,
        )

        repository.delete_by_id_prefix.assert_awaited_once_with(
            "confluence:page:123:chunk:"
        )
        service._generate_embeddings.assert_not_awaited()
        repository.store_with_embeddings.assert_not_awaited()

    async def test_incremental_sync_page_fetches_and_stores_only_claimed_record(self) -> None:
        service = self._build_service()
        transform_result = SimpleNamespace(documents=[SimpleNamespace(id="doc-page-123")])
        service.client = SimpleNamespace(
            get_page_by_id=AsyncMock(return_value=_raw_confluence_page("123")),
            get_blogpost_by_id=AsyncMock(),
        )
        service._load_space_context = AsyncMock(
            return_value=("space-1", "Docs", {"author-1": "Author One"})
        )
        service._process_page = AsyncMock(return_value=transform_result)
        service._store_transform_result = AsyncMock()
        service._sync_space_pages = AsyncMock(
            side_effect=AssertionError("incremental page sync must not call broad page sync")
        )
        service._sync_space_blogposts = AsyncMock(
            side_effect=AssertionError("incremental page sync must not call broad blogpost sync")
        )

        result = await service.incremental_sync(
            space_key="DOC",
            record_type="page",
            record_id="123",
            event_kind="updated",
            since=datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result, {"synced": 1, "errors": 0, "skipped": False})
        service.client.get_page_by_id.assert_awaited_once_with("123", body_format="storage")
        service.client.get_blogpost_by_id.assert_not_awaited()
        service._sync_space_pages.assert_not_awaited()
        service._sync_space_blogposts.assert_not_awaited()
        service._process_page.assert_awaited_once()
        service._store_transform_result.assert_awaited_once_with(
            entity_type="page",
            content_id="123",
            space_key="DOC",
            transform_result=transform_result,
            audit_context=None,
        )

    async def test_incremental_sync_blogpost_fetches_and_stores_only_claimed_record(self) -> None:
        service = self._build_service()
        transform_result = SimpleNamespace(documents=[SimpleNamespace(id="doc-blogpost-456")])
        service.client = SimpleNamespace(
            get_page_by_id=AsyncMock(),
            get_blogpost_by_id=AsyncMock(return_value=_raw_confluence_blogpost("456")),
        )
        service._load_space_context = AsyncMock(
            return_value=("space-1", "Docs", {"author-1": "Author One"})
        )
        service._process_blogpost = AsyncMock(return_value=transform_result)
        service._store_transform_result = AsyncMock()
        service._sync_space_pages = AsyncMock(
            side_effect=AssertionError("incremental blogpost sync must not call broad page sync")
        )
        service._sync_space_blogposts = AsyncMock(
            side_effect=AssertionError("incremental blogpost sync must not call broad blogpost sync")
        )

        result = await service.incremental_sync(
            space_key="DOC",
            record_type="blogpost",
            record_id="456",
            event_kind="updated",
            since=datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(result, {"synced": 1, "errors": 0, "skipped": False})
        service.client.get_page_by_id.assert_not_awaited()
        service.client.get_blogpost_by_id.assert_awaited_once_with(
            "456",
            body_format="storage",
        )
        service._sync_space_pages.assert_not_awaited()
        service._sync_space_blogposts.assert_not_awaited()
        service._process_blogpost.assert_awaited_once()
        service._store_transform_result.assert_awaited_once_with(
            entity_type="blogpost",
            content_id="456",
            space_key="DOC",
            transform_result=transform_result,
            audit_context=None,
        )
