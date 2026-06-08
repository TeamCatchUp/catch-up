from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.sync.ingestion import SyncExecutionRequest
from catchup.sync.ingestion import SyncExecutionResult
from catchup.sync.ingestion import SyncWindow


def test_sync_ingestion_contract_accepts_legacy_connector_key_values() -> None:
    request = SyncExecutionRequest(
        connector=ConnectorKey.JIRA,
        tenant_id="cloud-123",
        target="issue",
    )
    result = SyncExecutionResult(
        connector=ConnectorKey.JIRA,
        tenant_id="cloud-123",
        target="issue",
    )

    assert request.connector == ConnectorKey.JIRA
    assert result.connector == ConnectorKey.JIRA


def test_sync_window_rejects_reversed_bounds() -> None:
    try:
        SyncWindow(
            window_start=datetime(2026, 4, 22, tzinfo=timezone.utc),
            window_end=datetime(2026, 4, 21, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert "window_start must be less than or equal to window_end" in str(exc)
    else:
        raise AssertionError("SyncWindow accepted reversed bounds")
