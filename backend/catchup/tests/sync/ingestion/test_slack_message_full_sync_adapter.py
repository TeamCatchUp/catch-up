from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

from catchup.sync.ingestion.adapters.slack import SlackMessageFetchResult
from catchup.sync.ingestion.adapters.slack import SlackMessageFullSyncAdapter
from catchup.sync.ingestion.adapters.slack import SlackMessageFullSyncExecutionRequest
from catchup.sync.ingestion.adapters.slack import SlackMessagePersistResult
from catchup.sync.ingestion.adapters.slack import SlackMessageSummaryResult
from catchup.sync.ingestion.adapters.slack import SlackMessageTransformResult
from catchup.sync.ingestion.schemas import SyncWindow


def test_full_sync_build_result_counts_v2_failures() -> None:
    adapter = SlackMessageFullSyncAdapter(
        team_id="T123",
        client=SimpleNamespace(),
        repository=SimpleNamespace(),
    )
    now = datetime(2026, 6, 13, tzinfo=timezone.utc)
    execution = SlackMessageFullSyncExecutionRequest(
        tenant_id="T123",
        channel_id="C123",
        channel_name="general",
    )
    persisted = SlackMessagePersistResult(
        persisted_count=1,
        error_count=0,
        v2_error_count=1,
        v2_failed_ids=("slack:message:T123:C123:1711.0001",),
    )

    result = adapter.build_result(
        execution=execution,
        sync_window=SyncWindow(window_start=now, window_end=now),
        fetched=SlackMessageFetchResult(),
        transformed=SlackMessageTransformResult(),
        summary=SlackMessageSummaryResult(),
        persisted=persisted,
    )

    assert result.persisted_count == 1
    assert result.failed_count == 1
    assert result.v2_failed_count == 1
    assert result.v2_failed_ids == ("slack:message:T123:C123:1711.0001",)
