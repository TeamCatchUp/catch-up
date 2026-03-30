from __future__ import annotations

from datetime import datetime

from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange


def build_confluence_record_change(
    *,
    cloud_id: str,
    space_key: str,
    record_type: str,
    record_id: str,
    last_event_at: datetime,
) -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CONFLUENCE,
        scope_id=cloud_id.strip(),
        record_type=record_type.strip(),
        record_id=record_id.strip(),
        parent_type="space",
        parent_id=space_key.strip(),
        event_kind="updated",
        last_event_at=last_event_at,
    )
