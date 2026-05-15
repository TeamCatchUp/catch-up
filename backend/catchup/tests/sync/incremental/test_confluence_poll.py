from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.connectors.confluence.service import ConfluenceIngestionService
from catchup.db.models import SyncConnector
from catchup.sync.incremental.poll.confluence import _collect_deleted_blogpost_changes
from catchup.sync.incremental.poll.confluence import _collect_deleted_page_changes
from catchup.sync.incremental.poll.confluence import (
    _exclude_unrecovered_stale_deleted_keys,
)
from catchup.sync.incremental.poll.confluence import _filter_repeated_deleted_changes
from catchup.sync.incremental.resolve.confluence import build_confluence_record_change


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
