from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from catchup.db.models import SyncConnector

class SyncStatusEventType(StrEnum):
    SNAPSHOT = "snapshot"
    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    TARGET_STARTED = "target_started"
    TARGET_REQUEUED = "target_requeued"
    TARGET_COMPLETED = "target_completed"
    TARGET_FAILED = "target_failed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    HEARTBEAT = "heartbeat"

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True, frozen=True)
class SyncStatusStreamEvent:
    connector: SyncConnector
    job_id: str
    scope_id: str
    event_type: SyncStatusEventType
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector.value,
            "job_id": self.job_id,
            "scope_id": self.scope_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, raw: str) -> "SyncStatusStreamEvent":
        data = json.loads(raw)
        return cls(
            connector=SyncConnector(str(data["connector"])),
            job_id=str(data["job_id"]),
            scope_id=str(data["scope_id"]),
            event_type=SyncStatusEventType(str(data["event_type"])),
            timestamp=str(data["timestamp"]),
            payload=dict(data.get("payload") or {}),
        )
