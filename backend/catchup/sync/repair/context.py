from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncType
from catchup.db.sync import get_event
from catchup.db.sync import get_job
from catchup.sync.common.exceptions import SyncRequestError


ACTIVE_EVENT_STATUSES = {
    SyncEventStatus.PENDING,
    SyncEventStatus.IN_PROGRESS,
    SyncEventStatus.RETRYING,
}


@dataclass(slots=True, frozen=True)
class RecordRepairContext:
    event_id: str
    event_status: SyncEventStatus
    connector: SyncConnector
    scope_id: str
    target_id: str
    target_name: str
    sync_from_ts: str
    sync_from_dt: datetime


def _parse_sync_from_ts(sync_from_ts: str) -> datetime:
    try:
        return datetime.fromtimestamp(float(sync_from_ts), tz=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise SyncRequestError(
            "event sync_from_ts is invalid",
            code="invalid_event_metadata",
            metadata={"sync_from_ts": sync_from_ts},
        ) from exc


def load_record_repair_context(event_id: str) -> RecordRepairContext:
    normalized_event_id = event_id.strip()
    if not normalized_event_id:
        raise SyncRequestError("event_id is required", code="invalid_event_id")

    with SessionLocal() as db:
        event = get_event(db, normalized_event_id)
        if event is None:
            raise SyncRequestError(
                "sync event not found",
                code="event_not_found",
                metadata={"event_id": normalized_event_id},
            )

        job = get_job(db, event.job_id)
        if job is None:
            raise SyncRequestError(
                "sync job not found for event",
                code="event_job_not_found",
                metadata={"event_id": normalized_event_id},
            )

    if job.sync_type != SyncType.FULL:
        raise SyncRequestError(
            "manual retry supports full sync events only",
            code="unsupported_event_type",
            metadata={"event_id": normalized_event_id},
        )

    if event.status in ACTIVE_EVENT_STATUSES:
        raise SyncRequestError(
            "manual retry supports terminal events only",
            code="invalid_event_status",
            metadata={
                "event_id": normalized_event_id,
                "event_status": event.status.value,
            },
        )

    metadata = event.resource_metadata if isinstance(event.resource_metadata, dict) else {}
    scope_id = str(metadata.get("scope_id") or job.scope_id or "").strip()
    target_id = str(event.resource_id or "").strip()
    target_name = str(metadata.get("target_name") or target_id).strip()
    sync_from_ts = str(metadata.get("sync_from_ts") or "").strip()

    if not scope_id:
        raise SyncRequestError(
            "event scope_id is missing",
            code="invalid_event_metadata",
            metadata={"event_id": normalized_event_id},
        )
    if not target_id:
        raise SyncRequestError(
            "event target_id is missing",
            code="invalid_event_metadata",
            metadata={"event_id": normalized_event_id},
        )
    if not sync_from_ts:
        raise SyncRequestError(
            "event sync_from_ts is missing",
            code="invalid_event_metadata",
            metadata={"event_id": normalized_event_id},
        )

    return RecordRepairContext(
        event_id=normalized_event_id,
        event_status=event.status,
        connector=event.connector,
        scope_id=scope_id,
        target_id=target_id,
        target_name=target_name or target_id,
        sync_from_ts=sync_from_ts,
        sync_from_dt=_parse_sync_from_ts(sync_from_ts),
    )
