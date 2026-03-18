from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEvent
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJob
from catchup.db.models import SyncType
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
    normalized_sync_from_ts = sync_from_ts.strip()

    try:
        return datetime.fromtimestamp(float(normalized_sync_from_ts), tz=timezone.utc)
    except (TypeError, ValueError):
        pass

    try:
        parsed = datetime.fromisoformat(normalized_sync_from_ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SyncRequestError(
            "event sync_from_ts is invalid",
            code="invalid_event_metadata",
            metadata={"sync_from_ts": sync_from_ts},
        ) from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _metadata_text(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if value is None:
        return ""
    return str(value).strip()


def load_record_repair_context(event_id: str) -> RecordRepairContext:
    normalized_event_id = event_id.strip()
    if not normalized_event_id:
        raise SyncRequestError("event_id is required", code="invalid_event_id")

    with SessionLocal() as db:
        stmt = (
            select(SyncEvent, SyncJob)
            .outerjoin(SyncJob, SyncJob.job_id == SyncEvent.job_id)
            .where(SyncEvent.event_id == normalized_event_id)
        )
        row = db.execute(stmt).one_or_none()

        if row is None:
            raise SyncRequestError(
                "sync event not found",
                code="event_not_found",
                metadata={"event_id": normalized_event_id},
            )

        event, job = row
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
    scope_id = _metadata_text(metadata, "scope_id") or str(job.scope_id or "").strip()
    target_id = _metadata_text(metadata, "target_id") or str(event.resource_id or "").strip()
    target_name = _metadata_text(metadata, "target_name") or target_id
    sync_from_ts = _metadata_text(metadata, "sync_from_ts")

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
