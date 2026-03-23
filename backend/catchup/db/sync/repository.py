from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Sequence

from sqlalchemy import case
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import literal
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector
from catchup.db.models import SyncEvent
from catchup.db.models import SyncEventPublishStatus
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJob
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType


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


@dataclass(slots=True, frozen=True)
class SyncEventPublishResultInput:
    event_id: str
    stream_message_id: str


@dataclass(slots=True, frozen=True)
class SyncEventSummary:
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    embedding_tokens_used: int
    summary_tokens_used: int
    last_error: str | None = None


_ALLOWED_JOB_TRANSITIONS: dict[SyncJobStatus, set[SyncJobStatus]] = {
    SyncJobStatus.PENDING: {SyncJobStatus.IN_PROGRESS},
    SyncJobStatus.IN_PROGRESS: {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED},
}

_ALLOWED_EVENT_TRANSITIONS: dict[SyncEventStatus, set[SyncEventStatus]] = {
    SyncEventStatus.PENDING: {
        SyncEventStatus.IN_PROGRESS,
        SyncEventStatus.RETRYING,
    },
    SyncEventStatus.IN_PROGRESS: {
        SyncEventStatus.SUCCESS,
        SyncEventStatus.RETRYING,
        SyncEventStatus.FAILED,
    },
    SyncEventStatus.RETRYING: {
        SyncEventStatus.PENDING,
        SyncEventStatus.FAILED,
    },
    SyncEventStatus.SUCCESS: {
        SyncEventStatus.SUCCESS,
        SyncEventStatus.FAILED,
    },
    SyncEventStatus.FAILED: {
        SyncEventStatus.SUCCESS,
        SyncEventStatus.FAILED,
    },
}

_ALLOWED_EVENT_PUBLISH_TRANSITIONS: dict[
    SyncEventPublishStatus, set[SyncEventPublishStatus]
] = {
    SyncEventPublishStatus.PENDING: {
        SyncEventPublishStatus.PUBLISHING,
    },
    SyncEventPublishStatus.FAILED: {
        SyncEventPublishStatus.PUBLISHING,
    },
    SyncEventPublishStatus.PUBLISHED: {
        SyncEventPublishStatus.PUBLISHING,
    },
    SyncEventPublishStatus.PUBLISHING: {
        SyncEventPublishStatus.PUBLISHED,
        SyncEventPublishStatus.FAILED,
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


def _validate_event_publish_transition(
    from_statuses: Sequence[SyncEventPublishStatus],
    to_status: SyncEventPublishStatus,
) -> None:
    if not from_statuses:
        raise ValueError("from_statuses must not be empty")

    for from_status in from_statuses:
        if to_status not in _ALLOWED_EVENT_PUBLISH_TRANSITIONS.get(from_status, set()):
            raise ValueError(
                f"event publish transition not allowed: {from_status} -> {to_status}"
            )


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
    db.flush()
    return job


def get_job(db: Session, job_id: str) -> SyncJob | None:
    stmt = select(SyncJob).where(SyncJob.job_id == job_id)
    return db.execute(stmt).scalar_one_or_none()


def try_acquire_full_sync_scope_lock(
    db: Session,
    *,
    connector: SyncConnector,
    scope_id: str,
) -> bool:
    stmt = select(
        func.pg_try_advisory_xact_lock(
            func.hashtext(literal("full_sync_dispatch_scope")),
            func.hashtext(literal(f"{connector.value}:{scope_id}")),
        )
    )
    return bool(db.execute(stmt).scalar_one())


def find_active_full_sync_job(
    db: Session,
    *,
    connector: SyncConnector,
    scope_id: str,
) -> SyncJob | None:
    in_progress_stmt = (
        select(SyncJob)
        .where(
            SyncJob.connector == connector,
            SyncJob.scope_id == scope_id,
            SyncJob.sync_type == SyncType.FULL,
            SyncJob.status == SyncJobStatus.IN_PROGRESS,
        )
        .order_by(SyncJob.requested_at.desc())
        .limit(1)
    )
    in_progress_job = db.execute(in_progress_stmt).scalar_one_or_none()
    if in_progress_job is not None:
        return in_progress_job

    active_pending_events = exists(
        select(SyncEvent.event_id).where(
            SyncEvent.job_id == SyncJob.job_id,
            SyncEvent.status.in_(
                [
                    SyncEventStatus.PENDING,
                    SyncEventStatus.IN_PROGRESS,
                    SyncEventStatus.RETRYING,
                ]
            ),
            SyncEvent.publish_status.in_(
                [
                    SyncEventPublishStatus.PENDING,
                    SyncEventPublishStatus.PUBLISHING,
                    SyncEventPublishStatus.PUBLISHED,
                    SyncEventPublishStatus.FAILED,
                ]
            ),
        )
    )
    pending_stmt = (
        select(SyncJob)
        .where(
            SyncJob.connector == connector,
            SyncJob.scope_id == scope_id,
            SyncJob.sync_type == SyncType.FULL,
            SyncJob.status == SyncJobStatus.PENDING,
            active_pending_events,
        )
        .order_by(SyncJob.requested_at.desc())
        .limit(1)
    )
    return db.execute(pending_stmt).scalar_one_or_none()


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
    db.flush()
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
    db.flush()

    for event in events:
        db.refresh(event)

    return events


def get_event(db: Session, event_id: str) -> SyncEvent | None:
    stmt = select(SyncEvent).where(SyncEvent.event_id == event_id)
    return db.execute(stmt).scalar_one_or_none()


def list_retry_ready_events(
    db: Session,
    *,
    now: datetime | None = None,
    connector: SyncConnector | None = None,
    limit: int = 100,
) -> list[SyncEvent]:
    retry_at = _to_utc(now or _utc_now())
    stmt = select(SyncEvent).where(
        SyncEvent.status == SyncEventStatus.RETRYING,
        SyncEvent.next_retry_at.is_not(None),
        SyncEvent.next_retry_at <= retry_at,
    )
    if connector is not None:
        stmt = stmt.where(SyncEvent.connector == connector)

    stmt = stmt.order_by(
        SyncEvent.next_retry_at.asc(),
        SyncEvent.updated_at.asc(),
        SyncEvent.requested_at.asc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def _update_event_publish_status(
    db: Session,
    *,
    event_id: str,
    from_statuses: Sequence[SyncEventPublishStatus],
    to_status: SyncEventPublishStatus,
    stream_message_id: str | None = None,
    publish_error: str | None = None,
    increment_attempt: bool = False,
) -> int:
    _validate_event_publish_transition(from_statuses, to_status)

    now = _utc_now()
    values: dict[str, object] = {
        "publish_status": to_status,
        "updated_at": now,
    }
    if increment_attempt:
        values["publish_attempt"] = SyncEvent.publish_attempt + 1

    if to_status == SyncEventPublishStatus.PUBLISHING:
        values["stream_message_id"] = None
        values["published_at"] = None
        values["publish_error"] = None
    elif to_status == SyncEventPublishStatus.PUBLISHED:
        values["stream_message_id"] = stream_message_id
        values["published_at"] = now
        values["publish_error"] = publish_error
    elif to_status == SyncEventPublishStatus.FAILED:
        values["stream_message_id"] = None
        values["published_at"] = None
        values["publish_error"] = publish_error

    stmt = (
        update(SyncEvent)
        .where(
            SyncEvent.event_id == event_id,
            SyncEvent.publish_status.in_(list(from_statuses)),
        )
        .values(**values)
    )
    result = db.execute(stmt)
    return result.rowcount or 0


def claim_events_for_publish(
    db: Session,
    *,
    event_ids: Sequence[str],
) -> bool:
    for event_id in event_ids:
        updated = _update_event_publish_status(
            db,
            event_id=event_id,
            from_statuses=[
                SyncEventPublishStatus.PENDING,
                SyncEventPublishStatus.FAILED,
            ],
            to_status=SyncEventPublishStatus.PUBLISHING,
            stream_message_id=None,
            publish_error=None,
            increment_attempt=True,
        )
        if updated != 1:
            return False

    db.flush()
    return True


def claim_events_for_republish(
    db: Session,
    *,
    event_ids: Sequence[str],
) -> bool:
    for event_id in event_ids:
        updated = _update_event_publish_status(
            db,
            event_id=event_id,
            from_statuses=[SyncEventPublishStatus.PUBLISHED],
            to_status=SyncEventPublishStatus.PUBLISHING,
            stream_message_id=None,
            publish_error=None,
            increment_attempt=True,
        )
        if updated != 1:
            return False

    db.flush()
    return True


def record_event_publish_outcomes(
    db: Session,
    *,
    published: Sequence[SyncEventPublishResultInput],
    failed_event_ids: Sequence[str],
    publish_error: str | None,
) -> bool:
    for item in published:
        updated = _update_event_publish_status(
            db,
            event_id=item.event_id,
            from_statuses=[SyncEventPublishStatus.PUBLISHING],
            to_status=SyncEventPublishStatus.PUBLISHED,
            stream_message_id=item.stream_message_id,
            publish_error=None,
        )
        if updated != 1:
            return False

    for event_id in failed_event_ids:
        updated = _update_event_publish_status(
            db,
            event_id=event_id,
            from_statuses=[SyncEventPublishStatus.PUBLISHING],
            to_status=SyncEventPublishStatus.FAILED,
            stream_message_id=None,
            publish_error=publish_error,
        )
        if updated != 1:
            return False

    db.flush()
    return True


def list_events_by_job(
    db: Session,
    *,
    job_id: str,
    statuses: Sequence[SyncEventStatus] | None = None,
    limit: int | None = 500,
    offset: int = 0,
) -> list[SyncEvent]:
    stmt = select(SyncEvent).where(SyncEvent.job_id == job_id)

    if statuses:
        stmt = stmt.where(SyncEvent.status.in_(list(statuses)))

    stmt = stmt.order_by(SyncEvent.requested_at.asc()).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_events_by_job(db: Session, *, job_id: str) -> int:
    stmt = select(func.count(SyncEvent.event_id)).where(SyncEvent.job_id == job_id)
    return int(db.execute(stmt).scalar_one())


def summarize_events_by_job(db: Session, *, job_id: str) -> SyncEventSummary:
    stmt = select(
        func.count(SyncEvent.event_id),
        func.coalesce(
            func.sum(
                case(
                    (
                        SyncEvent.status.in_(
                            [SyncEventStatus.PENDING, SyncEventStatus.RETRYING]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case((SyncEvent.status == SyncEventStatus.IN_PROGRESS, 1), else_=0)
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    ((SyncEvent.status == SyncEventStatus.SUCCESS), 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(
            func.sum(
                case(
                    ((SyncEvent.status == SyncEventStatus.FAILED), 1),
                    else_=0,
                )
            ),
            0,
        ),
        func.coalesce(func.sum(SyncEvent.attempt), 0),
        func.coalesce(func.sum(SyncEvent.embedding_tokens_used), 0),
        func.coalesce(func.sum(SyncEvent.summary_tokens_used), 0),
    ).where(SyncEvent.job_id == job_id)
    row = db.execute(stmt).one()

    error_stmt = (
        select(
            func.coalesce(
                SyncEvent.last_error,
                SyncEvent.publish_error,
            )
        )
        .where(
            SyncEvent.job_id == job_id,
            SyncEvent.status == SyncEventStatus.FAILED,
            func.coalesce(
                SyncEvent.last_error,
                SyncEvent.publish_error,
            ).is_not(None),
        )
        .order_by(
            SyncEvent.failed_at.desc(),
            SyncEvent.updated_at.desc(),
            SyncEvent.requested_at.desc(),
        )
        .limit(1)
    )
    last_error = db.execute(error_stmt).scalar_one_or_none()

    return SyncEventSummary(
        total_targets=int(row[0]),
        queued_targets=int(row[1]),
        processing_targets=int(row[2]),
        completed_targets=int(row[3]),
        failed_targets=int(row[4]),
        requeued_targets=int(row[5]),
        embedding_tokens_used=int(row[6]),
        summary_tokens_used=int(row[7]),
        last_error=str(last_error) if last_error is not None else None,
    )


def has_successful_full_sync_event(
    db: Session,
    *,
    connector: SyncConnector,
    scope_id: str,
    resource_type: str,
    resource_id: str,
) -> bool:
    stmt = (
        select(SyncEvent.event_id)
        .join(SyncJob, SyncJob.job_id == SyncEvent.job_id)
        .where(
            SyncJob.connector == connector,
            SyncJob.scope_id == scope_id,
            SyncJob.sync_type == SyncType.FULL,
            SyncEvent.connector == connector,
            SyncEvent.resource_type == resource_type,
            SyncEvent.resource_id == resource_id,
            SyncEvent.status == SyncEventStatus.SUCCESS,
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def update_event_status_cas(
    db: Session,
    *,
    event_id: str,
    from_statuses: Sequence[SyncEventStatus],
    to_status: SyncEventStatus,
    embedding_tokens_used: int | None = None,
    summary_tokens_used: int | None = None,
    next_retry_at: datetime | None = None,
    last_error: str | None = None,
    increment_attempt: bool = False,
    retry_ready_at: datetime | None = None,
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

    if next_retry_at is not None or to_status != SyncEventStatus.RETRYING:
        values["next_retry_at"] = _to_utc(next_retry_at) if next_retry_at is not None else None

    if last_error is not None or to_status in {
        SyncEventStatus.PENDING,
        SyncEventStatus.IN_PROGRESS,
        SyncEventStatus.SUCCESS,
    }:
        values["last_error"] = last_error

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
    if retry_ready_at is not None:
        stmt = stmt.where(
            SyncEvent.next_retry_at.is_not(None),
            SyncEvent.next_retry_at <= _to_utc(retry_ready_at),
        )
    result = db.execute(stmt)
    db.flush()
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


def mark_event_retrying(
    db: Session,
    event_id: str,
    *,
    from_statuses: Sequence[SyncEventStatus] | None = None,
    next_retry_at: datetime | None = None,
    last_error: str | None = None,
    increment_attempt: bool = False,
) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=list(from_statuses or [SyncEventStatus.IN_PROGRESS]),
        to_status=SyncEventStatus.RETRYING,
        next_retry_at=next_retry_at,
        last_error=last_error,
        increment_attempt=increment_attempt,
    )


def requeue_retrying_event(
    db: Session,
    event_id: str,
    *,
    ready_at: datetime | None = None,
    require_due: bool = False,
) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.RETRYING],
        to_status=SyncEventStatus.PENDING,
        retry_ready_at=ready_at if require_due else None,
    )


def mark_event_failed(
    db: Session,
    event_id: str,
    *,
    last_error: str | None = None,
) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[SyncEventStatus.IN_PROGRESS, SyncEventStatus.RETRYING],
        to_status=SyncEventStatus.FAILED,
        last_error=last_error,
    )


def finalize_manual_retry_success(db: Session, event_id: str) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[
            SyncEventStatus.SUCCESS,
            SyncEventStatus.FAILED,
        ],
        to_status=SyncEventStatus.SUCCESS,
    )


def finalize_manual_retry_failed(db: Session, event_id: str) -> bool:
    return update_event_status_cas(
        db,
        event_id=event_id,
        from_statuses=[
            SyncEventStatus.SUCCESS,
            SyncEventStatus.FAILED,
        ],
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
    db.flush()

    return int(embedding_total), int(summary_total)
