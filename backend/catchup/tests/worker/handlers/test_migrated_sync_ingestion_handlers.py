from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import SyncEventKind
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.handlers.confluence import ConfluenceFullSyncHandler
from catchup.sync.handlers.confluence import ConfluenceIncrementalHandler
from catchup.sync.handlers.github import GithubFullSyncHandler
from catchup.sync.handlers.github import GithubIncrementalHandler
from catchup.sync.handlers.slack import SlackFullSyncHandler
from catchup.sync.handlers.slack import SlackIncrementalHandler


def _slack_full_context() -> FullSyncContext:
    return FullSyncContext(
        event_id="event-1",
        job_id="job-1",
        connector=SyncConnector.SLACK,
        scope_id="T123",
        target_type=SyncTargetType.CHANNEL,
        target_id="C123",
        target_name="general",
        attempt=0,
        max_attempts=3,
        sync_from_ts="1778899200.0",
    )


def _github_full_context() -> FullSyncContext:
    return FullSyncContext(
        event_id="event-4",
        job_id="job-1",
        connector=SyncConnector.GITHUB,
        scope_id="123",
        target_type=SyncTargetType.REPOSITORY,
        target_id="456",
        target_name="org/repo",
        attempt=0,
        max_attempts=3,
        sync_from_ts="1778899200.0",
        metadata={"stream_type": "issue", "repo_full_name": "org/repo"},
    )


def _confluence_full_context() -> FullSyncContext:
    return FullSyncContext(
        event_id="event-5",
        job_id="job-1",
        connector=SyncConnector.CONFLUENCE,
        scope_id="cloud-123",
        target_type=SyncTargetType.SPACE,
        target_id="ENG",
        target_name="Engineering",
        attempt=0,
        max_attempts=3,
        sync_from_ts="1778899200.0",
        metadata={"content_type": "page", "space_name": "Engineering"},
    )


def _slack_incremental_context() -> IncrementalSyncContext:
    return IncrementalSyncContext(
        event_id="event-6",
        job_id="job-1",
        connector=SyncConnector.SLACK,
        scope_id="T123",
        target_type=SyncTargetType.CHANNEL,
        target_id="C123",
        target_name="general",
        attempt=0,
        max_attempts=3,
        record_key="slack:T123:channel:C123:message:1700000000.000000",
        generation=1,
        record_type="message",
        record_id="1700000000.000000",
        parent_type=SyncTargetType.CHANNEL,
        parent_id="C123",
        event_kind=SyncEventKind.UPDATED,
        last_event_at="2026-05-16T00:00:00+00:00",
    )


def _github_incremental_context() -> IncrementalSyncContext:
    return IncrementalSyncContext(
        event_id="event-2",
        job_id="job-1",
        connector=SyncConnector.GITHUB,
        scope_id="123",
        target_type=SyncTargetType.REPOSITORY,
        target_id="456",
        target_name="org/repo",
        attempt=0,
        max_attempts=3,
        record_key="github:123:repository:456:issue:7",
        generation=1,
        record_type="issue",
        record_id="7",
        parent_type=SyncTargetType.REPOSITORY,
        parent_id="456",
        event_kind=SyncEventKind.DELETED,
        last_event_at="2026-05-16T00:00:00+00:00",
    )


def _confluence_incremental_context() -> IncrementalSyncContext:
    return IncrementalSyncContext(
        event_id="event-3",
        job_id="job-1",
        connector=SyncConnector.CONFLUENCE,
        scope_id="cloud-123",
        target_type=SyncTargetType.SPACE,
        target_id="ENG",
        target_name="Engineering",
        attempt=0,
        max_attempts=3,
        record_key="confluence:cloud-123:space:ENG:page:1001",
        generation=1,
        record_type="page",
        record_id="1001",
        parent_type=SyncTargetType.SPACE,
        parent_id="ENG",
        event_kind=SyncEventKind.DELETED,
        last_event_at="2026-05-16T00:00:00+00:00",
    )


class MigratedSyncIngestionHandlerTests(IsolatedAsyncioTestCase):
    async def test_slack_full_sync_uses_sync_ingestion_execution(self) -> None:
        handler = SlackFullSyncHandler()
        service = SimpleNamespace()
        core_result = SimpleNamespace(
            persisted_count=3,
            deleted_count=0,
            failed_count=0,
            skipped=False,
            is_last=True,
            next_cursor=None,
        )

        with (
            patch(
                "catchup.sync.handlers.slack.create_slack_message_full_sync_adapter",
                AsyncMock(return_value=service),
            ),
            patch(
                "catchup.sync.handlers.slack.run_sync_ingestion",
                AsyncMock(return_value=core_result),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(context=_slack_full_context(), service_cache={})

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        sync_window = run_sync_ingestion.await_args.kwargs["sync_window"]
        self.assertEqual(execution.channel_id, "C123")
        self.assertEqual(execution.channel_name, "general")
        self.assertFalse(hasattr(execution, "sync_from_ts"))
        self.assertEqual(sync_window.window_start.timestamp(), 1778899200.0)
        self.assertEqual(result.synced_count, 3)

    async def test_github_full_sync_uses_sync_ingestion_stream_target(self) -> None:
        handler = GithubFullSyncHandler()
        adapter = SimpleNamespace()
        core_result = SimpleNamespace(
            persisted_count=1,
            deleted_count=0,
            failed_count=0,
            v2_failed_count=0,
            v2_failed_ids=(),
            skipped=False,
            is_last=True,
        )

        with (
            patch(
                "catchup.sync.handlers.github.create_github_repository_full_sync_adapter",
                AsyncMock(return_value=adapter),
            ),
            patch(
                "catchup.sync.handlers.github.run_sync_ingestion",
                AsyncMock(return_value=core_result),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(
                context=_github_full_context(),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        self.assertEqual(execution.record_type, "issue")
        self.assertEqual(execution.repo_full_name, "org/repo")
        self.assertEqual(result.synced_count, 1)

    async def test_github_full_sync_forwards_next_cursor_between_pages(self) -> None:
        handler = GithubFullSyncHandler()
        adapter = SimpleNamespace()
        first_result = SimpleNamespace(
            persisted_count=1,
            deleted_count=0,
            failed_count=0,
            v2_failed_count=0,
            v2_failed_ids=(),
            skipped=False,
            is_last=False,
            next_cursor="cursor-2",
        )
        second_result = SimpleNamespace(
            persisted_count=1,
            deleted_count=0,
            failed_count=0,
            v2_failed_count=0,
            v2_failed_ids=(),
            skipped=False,
            is_last=True,
            next_cursor=None,
        )

        with (
            patch(
                "catchup.sync.handlers.github.create_github_repository_full_sync_adapter",
                AsyncMock(return_value=adapter),
            ),
            patch(
                "catchup.sync.handlers.github.run_sync_ingestion",
                AsyncMock(side_effect=[first_result, second_result]),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(
                context=_github_full_context(),
                service_cache={},
            )

        self.assertEqual(run_sync_ingestion.await_count, 2)
        first_execution = run_sync_ingestion.await_args_list[0].kwargs["execution"]
        second_execution = run_sync_ingestion.await_args_list[1].kwargs["execution"]
        self.assertIsNone(first_execution.after_cursor)
        self.assertEqual(first_execution.batch_index, 0)
        self.assertEqual(second_execution.after_cursor, "cursor-2")
        self.assertEqual(second_execution.batch_index, 1)
        self.assertEqual(result.synced_count, 2)

    async def test_confluence_full_sync_uses_sync_ingestion_content_target(self) -> None:
        handler = ConfluenceFullSyncHandler()
        dependencies = SimpleNamespace(
            cloud_id="cloud-123",
            site_url="",
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            transformer=SimpleNamespace(),
        )
        core_result = SimpleNamespace(
            persisted_count=1,
            deleted_count=0,
            failed_count=0,
            v2_failed_count=0,
            v2_failed_ids=(),
            skipped=False,
            transformed=SimpleNamespace(stop_after_batch=False),
            is_last=True,
        )

        with (
            patch(
                "catchup.sync.handlers.confluence.create_confluence_space_sync_dependencies",
                AsyncMock(return_value=dependencies),
            ),
            patch(
                "catchup.sync.handlers.confluence.run_sync_ingestion",
                AsyncMock(return_value=core_result),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(
                context=_confluence_full_context(),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        self.assertEqual(execution.record_type, "page")
        self.assertEqual(execution.space_key, "ENG")
        self.assertEqual(result.synced_count, 1)

    async def test_slack_incremental_uses_sync_ingestion_exact_record(self) -> None:
        handler = SlackIncrementalHandler()
        core_result = SimpleNamespace(
            persisted_count=1,
            deleted_count=0,
            failed_count=0,
            skipped=False,
        )

        with (
            patch(
                "catchup.sync.handlers.slack.create_slack_message_incremental_sync_adapter",
                AsyncMock(return_value=SimpleNamespace()),
            ),
            patch(
                "catchup.sync.handlers.slack.run_sync_ingestion",
                AsyncMock(return_value=core_result),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(
                context=_slack_incremental_context(),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        self.assertEqual(execution.channel_id, "C123")
        self.assertEqual(execution.record_id, "1700000000.000000")
        self.assertEqual(execution.event_kind, "updated")
        self.assertFalse(hasattr(execution, "sync_from"))
        self.assertEqual(result.synced_count, 1)

    async def test_github_incremental_uses_sync_ingestion_exact_record(self) -> None:
        handler = GithubIncrementalHandler()
        core_result = SimpleNamespace(
            persisted_count=0,
            deleted_count=1,
            failed_count=0,
            skipped=False,
        )

        with (
            patch(
                "catchup.sync.handlers.github.create_github_repository_incremental_sync_adapter",
                AsyncMock(return_value=SimpleNamespace()),
            ),
            patch(
                "catchup.sync.handlers.github.run_sync_ingestion",
                AsyncMock(return_value=core_result),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(
                context=_github_incremental_context(),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        self.assertEqual(execution.repo_id, 456)
        self.assertEqual(execution.record_type, "issue")
        self.assertEqual(execution.record_id, "7")
        self.assertEqual(execution.event_kind, "deleted")
        self.assertEqual(result.synced_count, 1)

    async def test_confluence_incremental_uses_sync_ingestion_deleted_record(self) -> None:
        handler = ConfluenceIncrementalHandler()
        dependencies = SimpleNamespace(
            cloud_id="cloud-123",
            site_url="",
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            transformer=SimpleNamespace(),
        )
        core_result = SimpleNamespace(
            persisted_count=0,
            deleted_count=1,
            failed_count=0,
            skipped=False,
        )

        with (
            patch(
                "catchup.sync.handlers.confluence.create_confluence_space_sync_dependencies",
                AsyncMock(return_value=dependencies),
            ),
            patch(
                "catchup.sync.handlers.confluence.run_sync_ingestion",
                AsyncMock(return_value=core_result),
            ) as run_sync_ingestion,
        ):
            result = await handler.handle(
                context=_confluence_incremental_context(),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        self.assertEqual(execution.space_key, "ENG")
        self.assertEqual(execution.record_type, "page")
        self.assertEqual(execution.record_id, "1001")
        self.assertEqual(execution.event_kind, "deleted")
        self.assertEqual(result.synced_count, 1)
