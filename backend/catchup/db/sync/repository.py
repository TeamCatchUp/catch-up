from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from catchup.db.models import (
    SyncConnector,
    SyncEvent,
    SyncEventStatus,
    SyncJob,
    SyncJobStatus,
    SyncType,
)


@dataclass(slots=True, frozen=True)
class SyncJobCreateInput:
    job_id: str
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    requested_at: datetime


@dataclass(slots=True, frozen=True)
class SyncEventCreateInput:
    event_id: str
    job_id: str
    connector: SyncConnector
    resource_type: str
    resource_id: str
    requested_at: datetime
    resource_metadata: dict[str, object] | None = None
    max_attempts: int = 3


_ALLOWED_JOB_TRANSITIONS: dict[SyncJobStatus, set[SyncJobStatus]] = {
    SyncJobStatus.PENDING: {SyncJobStatus.IN_PROGRESS},
    SyncJobStatus.IN_PROGRESS: {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED},
}

_ALLOWED_EVENT_TRANSITIONS: dict[SyncEventStatus, set[SyncEventStatus]] = {
    SyncEventStatus.PENDING: {SyncEventStatus.IN_PROGRESS},
    SyncEventStatus.IN_PROGRESS: {
        SyncEventStatus.SUCCESS,
        SyncEventStatus.RETRYING,
        SyncEventStatus.FAILED,
    },
    SyncEventStatus.RETRYING: {
        SyncEventStatus.PENDING,
        SyncEventStatus.FAILED,
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_job_transition(
    from_statuses: Sequence[SyncJobStatus],
    to_status: SyncJobStatus,
) -> None:
    if not from_statuses:
        raise ValueError("from_statuses must not be empty")

    for from_status in from_statuses:
        if to_status not in _ALLOWED_JOB_TRANSITIONS.get(from_status, set()):
            raise ValueError(f"job transition not allowed: {from_status} -> {to_status}")


def _validate_event_transition(
    from_statuses: Sequence[SyncEventStatus],
    to_status: SyncEventStatus,
) -> None:
    if not from_statuses:
        raise ValueError("from_statuses must not be empty")

    for from_status in from_statuses:
        if to_status not in _ALLOWED_EVENT_TRANSITIONS.get(from_status, set()):
            raise ValueError(f"event transition not allowed: {from_status} -> {to_status}")


def create_job(db: Session, payload: SyncJobCreateInput) -> SyncJob:
    job = SyncJob(
        job_id=payload.job_id,
        connector=payload.connector,
        sync_type=payload.sync_type,
        scope_id=payload.scope_id,
        status=SyncJobStatus.PENDING,
        requested_at=_to_utc(payload.requested_at),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> SyncJob | None:
    stmt = select(SyncJob).where(SyncJob.job_id == job_id)
    return db.execute(stmt).scalar_one_or_none()


def list_jobs(
    db: Session,
    *,
    connector: SyncConnector | None = None,
    statuses: Sequence[SyncJobStatus] | None = None,
    limit: int = 100,
) -> list[SyncJob]:
    stmt = select(SyncJob)

    if connector is not None:
        stmt = stmt.where(SyncJob.connector == connector)

    if statuses:
        stmt = stmt.where(SyncJob.status.in_(list(statuses)))

    stmt = stmt.order_by(SyncJob.requested_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_job_status_cas(
    db: Session,
    *,
    job_id: str,
    from_statuses: Sequence[SyncJobStatus],
    to_status: SyncJobStatus,
    embedding_tokens_used: int | None = None,
    summary_tokens_used: int | None = None,
) -> bool:
    _validate_job_transition(from_statuses, to_status)

    now = _utc_now()
    values: dict[str, object] = {"status": to_status, "updated_at": now}

    if to_status == SyncJobStatus.IN_PROGRESS:
        values["started_at"] = now
        values["succeeded_at"] = None
        values["failed_at"] = None
    elif to_status == SyncJobStatus.SUCCESS:
        values["succeeded_at"] = now
        values["failed_at"] = None
    elif to_status == SyncJobStatus.FAILED:
        values["failed_at"] = now
        values["succeeded_at"] = None

    if embedding_tokens_used is not None:
        values["embedding_tokens_used"] = embedding_tokens_used
    if summary_tokens_used is not None:
        values["summary_tokens_used"] = summary_tokens_used

    stmt = (
        update(SyncJob)
        .where(
            SyncJob.job_id == job_id,
            SyncJob.status.in_(list(from_statuses)),
        )
        .values(**values)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount == 1


def start_job(db: Session, job_id: str) -> bool:
    return update_job_status_cas(
        db,
        job_id=job_id,
        from_statuses=[SyncJobStatus.PENDING],
        to_status=SyncJobStatus.IN_PROGRESS,
    )


def complete_job_success(db: Session, job_id: str) -> bool:
    return update_job_status_cas(
        db,
        job_id=job_id,
        from_statuses=[SyncJobStatus.IN_PROGRESS],
        to_status=SyncJobStatus.SUCCESS,
    )


def complete_job_failed(db: Session, job_id: str) -> bool:
    return update_job_status_cas(
        db,
        job_id=job_id,
        from_statuses=[SyncJobStatus.IN_PROGRESS],
        to_status=SyncJobStatus.FAILED,
    )


def create_events(db: Session, payloads: Sequence[SyncEventCreateInput]) -> list[SyncEvent]:
    if not payloads:
        return []

    events = [
        SyncEvent(
            event_id=item.event_id,
            job_id=item.job_id,
            connector=item.connector,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            resource_metadata=item.resource_metadata or {},
            status=SyncEventStatus.PENDING,
            attempt=0,
            max_attempts=item.max_attempts,
            requested_at=_to_utc(item.requested_at),
        )
        for item in payloads
    ]

    db.add_all(events)
    db.commit()

    for event in events:
        db.refresh(event)

    return events


def get_event(db: Session, event_id: str) -> SyncEvent | None:
    stmt = select(SyncEvent).where(SyncEvent.event_id == event_id)
    return db.execute(stmt).scalar_one_or_none()


def list_events_by_job(
    db: Session,
    *,
    job_id: str,
    statuses: Sequence[SyncEventStatus] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[SyncEvent]:
    stmt = select(SyncEvent).where(SyncEvent.job_id == job_id)

    if statuses:
        stmt = stmt.where(SyncEvent.status.in_(list(statuses)))

    stmt = stmt.order_by(SyncEvent.requested_at.asc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_event_status_cas(
    db: Session,
    *,
    event_id: str,
    from_statuses: Sequence[SyncEventStatus],
    to_status: SyncEventStatus,
    embedding_tokens_used: int | None = None,
    summary_tokens_used: int | None = None,
    increment_attempt: bool = False,
) -> bool:
    _validate_event_transition(from_statuses, to_status)

    now = _utc_now()
    values: dict[str, object] = {"status": to_status, "updated_at": now}

    if to_status == SyncEventStatus.PENDING:
        values["started_at"] = None
        values["succeeded_at"] = None
        values["failed_at"] = None
    elif to_status == SyncEventStatus.IN_PROGRESS:
        values["started_at"] = now
        values["succeeded_at"] = None
        values["failed_at"] = None
    elif to_status == SyncEventStatus.SUCCESS:
        values["succeeded_at"] = now
        values["failed_at"] = None
    elif to_status == SyncEventStatus.FAILED:
        values["failed_at"] = now
        values["succeeded_at"] = None
    elif to_status == SyncEventStatus.RETRYING:
        values["failed_at"] = None
        values["succeeded_at"] = None

    if embedding_tokens_used is not None:
        values["embedding_tokens_used"] = embedding_tokens_used
    if summary_tokens_used is not None:
        values["summary_tokens_used"] = summary_tokens_used

    if increment_attempt:
        values["attempt"] = SyncEvent.attempt + 1

    stmt = (
        update(SyncEvent)
        .where(
            SyncEvent.event_id == event_id,
            SyncEvent.status.in_(list(from_statuses)),
        )
        .values(**values)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount == 1


def claim_event_for_processing(db: Session, event_id: str) -> bool:
    # Worker 처리권 획득: PENDING에서만 IN_PROGRESS로 전이한다.
    # RETRYING 이벤트는 requeue_retrying_event()로 PENDING 전이 후 claim해야 한다.
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.PENDING],
        to_status=SyncEventStatus.IN_PROGRESS,
    )


def mark_event_success(
    db: Session,
    *,
    event_id: str,
    embedding_tokens_used: int = 0,
    summary_tokens_used: int = 0,
) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.IN_PROGRESS],
        to_status=SyncEventStatus.SUCCESS,
        embedding_tokens_used=embedding_tokens_used,
        summary_tokens_used=summary_tokens_used,
    )


def mark_event_retrying(db: Session, event_id: str) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.IN_PROGRESS],
        to_status=SyncEventStatus.RETRYING,
    )


def requeue_retrying_event(db: Session, event_id: str) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.RETRYING],
        to_status=SyncEventStatus.PENDING,
        increment_attempt=True,
    )


def mark_event_failed(db: Session, event_id: str) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.IN_PROGRESS, SyncEventStatus.RETRYING],
        to_status=SyncEventStatus.FAILED,
    )


def refresh_job_token_usage(db: Session, job_id: str) -> tuple[int, int]:
    # Event별 토큰 사용량을 Job 집계값으로 동기화
    stmt = select(
        func.coalesce(func.sum(SyncEvent.embedding_tokens_used), 0),
        func.coalesce(func.sum(SyncEvent.summary_tokens_used), 0),
    ).where(SyncEvent.job_id == job_id)
    embedding_total, summary_total = db.execute(stmt).one()

    db.execute(
        update(SyncJob)
        .where(SyncJob.job_id == job_id)
        .values(
            embedding_tokens_used=int(embedding_total),
            summary_tokens_used=int(summary_total),
            updated_at=_utc_now(),
        )
    )
    db.commit()

    return int(embedding_total), int(summary_total)
