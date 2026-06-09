from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import SyncEventKind
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.handlers.jira import JiraIncrementalHandler

_HANDLER_MODULE = "catchup.sync.handlers.jira"


def _context() -> IncrementalSyncContext:
    return IncrementalSyncContext(
        event_id="event-123",
        job_id="job-123",
        connector=SyncConnector.JIRA,
        scope_id="cloud-123",
        target_type=SyncTargetType.PROJECT,
        target_id="GRT",
        target_name="GRT",
        attempt=0,
        max_attempts=3,
        record_key="jira:cloud-123:project:GRT:issue:GRT-1",
        generation=1,
        record_type="issue",
        record_id="GRT-1",
        parent_type=SyncTargetType.PROJECT,
        parent_id="GRT",
        event_kind=SyncEventKind.UPDATED,
        last_event_at="2026-05-08T05:00:00+00:00",
    )


class JiraIncrementalHandlerTests(IsolatedAsyncioTestCase):
    async def test_jira_incremental_sync_uses_exact_issue_path_only(self) -> None:
        handler = JiraIncrementalHandler()
        result = SimpleNamespace(
            error_count=0,
            persisted_count=1,
            deleted_count=0,
            skipped=False,
        )

        with (
            patch(
                f"{_HANDLER_MODULE}.create_jira_issue_ingestion_dependencies",
                AsyncMock(return_value=SimpleNamespace()),
            ),
            patch(
                f"{_HANDLER_MODULE}.prepare_jira_issue_transform_context",
                AsyncMock(),
            ),
            patch(
                f"{_HANDLER_MODULE}.run_sync_ingestion",
                AsyncMock(return_value=result),
            ) as run_sync_ingestion,
            patch(
                "catchup.sync.ingestion.services.jira.JiraIngestionService.incremental_sync",
                AsyncMock(),
            ) as legacy_incremental_sync,
        ):
            sync_result = await handler.handle(
                context=_context(),
                service_cache={},
            )

        run_sync_ingestion.assert_awaited_once()
        execution = run_sync_ingestion.await_args.kwargs["execution"]
        self.assertEqual(execution.project_key, "GRT")
        self.assertEqual(execution.issue_key, "GRT-1")
        legacy_incremental_sync.assert_not_awaited()
        self.assertEqual(sync_result.synced_count, 1)
