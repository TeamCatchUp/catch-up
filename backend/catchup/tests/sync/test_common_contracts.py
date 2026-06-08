from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.sync.common import EventSyncResult
from catchup.sync.common import FullSyncContext
from catchup.sync.common import IncrementalSyncContext
from catchup.sync.common import PageIngestionRequest
from catchup.sync.common import PageSyncResult
from catchup.sync.common import RecordIngestionRequest
from catchup.sync.common import SyncEventKind
from catchup.sync.common import SyncTargetType
from catchup.sync.common import TargetSyncResult
from catchup.sync.common.context import FullSyncContext as ContextFullSyncContext
from catchup.sync.common.context import (
    IncrementalSyncContext as ContextIncrementalSyncContext,
)
from catchup.sync.common.results import TargetSyncResult as ResultsTargetSyncResult
from catchup.sync.common.schemas import FullSyncContext as SchemaFullSyncContext
from catchup.sync.common.schemas import (
    IncrementalSyncContext as SchemaIncrementalSyncContext,
)
from catchup.sync.common.schemas import TargetSyncResult as SchemaTargetSyncResult


def test_common_schema_imports_are_compatibility_reexports() -> None:
    assert SchemaFullSyncContext is ContextFullSyncContext
    assert SchemaIncrementalSyncContext is ContextIncrementalSyncContext
    assert SchemaTargetSyncResult is ResultsTargetSyncResult


def test_target_sync_result_remains_existing_worker_result_shape() -> None:
    result = TargetSyncResult(synced_count=2, error_count=1, skipped=True)

    assert isinstance(result, EventSyncResult)
    assert result == TargetSyncResult(
        synced_count=2,
        error_count=1,
        skipped=True,
    )


def test_page_and_record_ingestion_requests_keep_context_separate() -> None:
    context = FullSyncContext(
        event_id="event-1",
        job_id="job-1",
        connector=SyncConnector.SLACK,
        scope_id="team-1",
        target_type=SyncTargetType.CHANNEL,
        target_id="channel-1",
        target_name="general",
        attempt=0,
        max_attempts=3,
        sync_from_ts=None,
    )

    page_request = PageIngestionRequest(
        context=context,
        page={"records": []},
    )
    record_request = RecordIngestionRequest(
        context=context,
        record={"id": "record-1"},
    )

    assert page_request.context is context
    assert record_request.context is context
    assert PageSyncResult(synced_count=1).synced_count == 1


def test_incremental_context_normalizes_incremental_fields() -> None:
    context = IncrementalSyncContext(
        event_id="event-1",
        job_id="job-1",
        connector="jira",
        scope_id="cloud-1",
        target_type="project",
        target_id="PROJ",
        target_name="Project",
        attempt=0,
        max_attempts=3,
        record_key="jira:PROJ-1",
        generation=1,
        parent_type="project",
        parent_id="PROJ",
        event_kind="deleted",
        last_event_at="2026-06-08T00:00:00Z",
    )

    assert context.connector is SyncConnector.JIRA
    assert context.target_type is SyncTargetType.PROJECT
    assert context.parent_type is SyncTargetType.PROJECT
    assert context.event_kind is SyncEventKind.DELETED
