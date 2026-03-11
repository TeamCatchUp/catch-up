from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.db.models import (
    IncrementalOutboxStatus,
    IncrementalRecordState,
    IncrementalRecordStatus,
    IncrementalStreamOutbox,
    SyncConnector,
)


@dataclass(slots=True, frozen=True)
class IncrementalRecordChangeInput:
    record_key: str
    connector: SyncConnector
    scope_id: str
    record_type: str
    record_id: str
    parent_type: str
    parent_id: str
    event_kind: str
    last_event_at: datetime
    debounce_until: datetime


@dataclass(slots=True, frozen=True)
class IncrementalOutboxCreateInput:
    record_key: str
    generation: int
    connector: SyncConnector
    scope_id: str
    parent_type: str
    parent_id: str
    event_kind: str


_ALLOWED_RECORD_TRANSITIONS: dict[IncrementalRecordStatus, set[IncrementalRecordStatus]] = {
    IncrementalRecordStatus.DEBOUNCING: {
        IncrementalRecordStatus.QUEUED,
        IncrementalRecordStatus.DEBOUNCING,
    },
    IncrementalRecordStatus.QUEUED: {
        IncrementalRecordStatus.PROCESSING,
        IncrementalRecordStatus.DEBOUNCING,
    },
    IncrementalRecordStatus.PROCESSING: {
        IncrementalRecordStatus.SYNCED,
        IncrementalRecordStatus.RETRY_WAIT,
        IncrementalRecordStatus.DEAD,
    },
    IncrementalRecordStatus.RETRY_WAIT: {
        IncrementalRecordStatus.QUEUED,
        IncrementalRecordStatus.DEBOUNCING,
        IncrementalRecordStatus.DEAD,
    },
    IncrementalRecordStatus.DEAD: {
        IncrementalRecordStatus.DEBOUNCING,
    },
    IncrementalRecordStatus.SYNCED: {
        IncrementalRecordStatus.DEBOUNCING,
    },
}

_ALLOWED_OUTBOX_TRANSITIONS: dict[IncrementalOutboxStatus, set[IncrementalOutboxStatus]] = {
    IncrementalOutboxStatus.PENDING: {
        IncrementalOutboxStatus.PUBLISHING,
        IncrementalOutboxStatus.FAILED,
    },
    IncrementalOutboxStatus.FAILED: {
        IncrementalOutboxStatus.PENDING,
        IncrementalOutboxStatus.PUBLISHING,
    },
    IncrementalOutboxStatus.PUBLISHING: {
        IncrementalOutboxStatus.PUBLISHED,
        IncrementalOutboxStatus.SKIPPED,
        IncrementalOutboxStatus.FAILED,
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _validate_record_transition(
    from_statuses: Sequence[IncrementalRecordStatus],
    to_status: IncrementalRecordStatus,
) -> None:
    if not from_statuses:
        raise ValueError("from_statuses must not be empty")

    for from_status in from_statuses:
        if to_status not in _ALLOWED_RECORD_TRANSITIONS.get(from_status, set()):
            raise ValueError(f"record transition not allowed: {from_status} -> {to_status}")


def _validate_outbox_transition(
    from_statuses: Sequence[IncrementalOutboxStatus],
    to_status: IncrementalOutboxStatus,
) -> None:
    if not from_statuses:
        raise ValueError("from_statuses must not be empty")

    for from_status in from_statuses:
        if to_status not in _ALLOWED_OUTBOX_TRANSITIONS.get(from_status, set()):
            raise ValueError(f"outbox transition not allowed: {from_status} -> {to_status}")


def get_record_state(db: Session, record_key: str) -> IncrementalRecordState | None:
    stmt = select(IncrementalRecordState).where(
        IncrementalRecordState.record_key == _normalize_text(record_key, "record_key")
    )
    return db.execute(stmt).scalar_one_or_none()


def upsert_record_change(
    db: Session,
    payload: IncrementalRecordChangeInput,
) -> IncrementalRecordState:
    now = _utc_now()
    stmt = insert(IncrementalRecordState).values(
        record_key=_normalize_text(payload.record_key, "record_key"),
        connector=payload.connector,
        scope_id=_normalize_text(payload.scope_id, "scope_id"),
        record_type=_normalize_text(payload.record_type, "record_type"),
        record_id=_normalize_text(payload.record_id, "record_id"),
        parent_type=_normalize_text(payload.parent_type, "parent_type"),
        parent_id=_normalize_text(payload.parent_id, "parent_id"),
        event_kind=_normalize_text(payload.event_kind, "event_kind"),
        status=IncrementalRecordStatus.DEBOUNCING,
        generation=1,
        attempt=0,
        last_event_at=_to_utc(payload.last_event_at),
        debounce_until=_to_utc(payload.debounce_until),
        next_retry_at=None,
        queued_generation=None,
        processing_generation=None,
        last_synced_at=None,
        last_error=None,
        lease_owner=None,
        lease_until=None,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[IncrementalRecordState.record_key],
        set_={
            "connector": payload.connector,
            "scope_id": _normalize_text(payload.scope_id, "scope_id"),
            "record_type": _normalize_text(payload.record_type, "record_type"),
            "record_id": _normalize_text(payload.record_id, "record_id"),
            "parent_type": _normalize_text(payload.parent_type, "parent_type"),
            "parent_id": _normalize_text(payload.parent_id, "parent_id"),
            "event_kind": _normalize_text(payload.event_kind, "event_kind"),
            "status": IncrementalRecordStatus.DEBOUNCING,
            "generation": IncrementalRecordState.generation + 1,
            "attempt": 0,
            "last_event_at": _to_utc(payload.last_event_at),
            "debounce_until": _to_utc(payload.debounce_until),
            "next_retry_at": None,
            "last_error": None,
            "lease_owner": None,
            "lease_until": None,
            "updated_at": now,
        },
    )
    db.execute(stmt)
    db.commit()
    state = get_record_state(db, payload.record_key)
    if state is None:
        raise RuntimeError("failed to upsert incremental record state")
    return state


def list_debounce_ready_records(
    db: Session,
    *,
    now: datetime | None = None,
    connector: SyncConnector | None = None,
    limit: int = 100,
) -> list[IncrementalRecordState]:
    ready_at = _to_utc(now or _utc_now())
    stmt: Select[tuple[IncrementalRecordState]] = select(IncrementalRecordState).where(
        IncrementalRecordState.status == IncrementalRecordStatus.DEBOUNCING,
        IncrementalRecordState.debounce_until <= ready_at,
    )
    if connector is not None:
        stmt = stmt.where(IncrementalRecordState.connector == connector)

    stmt = stmt.order_by(
        IncrementalRecordState.debounce_until.asc(),
        IncrementalRecordState.updated_at.asc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_retry_ready_records(
    db: Session,
    *,
    now: datetime | None = None,
    connector: SyncConnector | None = None,
    limit: int = 100,
) -> list[IncrementalRecordState]:
    retry_at = _to_utc(now or _utc_now())
    stmt: Select[tuple[IncrementalRecordState]] = select(IncrementalRecordState).where(
        IncrementalRecordState.status == IncrementalRecordStatus.RETRY_WAIT,
        IncrementalRecordState.next_retry_at.is_not(None),
        IncrementalRecordState.next_retry_at <= retry_at,
    )
    if connector is not None:
        stmt = stmt.where(IncrementalRecordState.connector == connector)

    stmt = stmt.order_by(
        IncrementalRecordState.next_retry_at.asc(),
        IncrementalRecordState.updated_at.asc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_parent_cohort_records(
    db: Session,
    *,
    connector: SyncConnector,
    scope_id: str,
    parent_type: str,
    parent_id: str,
    max_generation: int,
    statuses: Sequence[IncrementalRecordStatus] | None = None,
    limit: int = 1000,
) -> list[IncrementalRecordState]:
    target_statuses = list(
        statuses
        or [
            IncrementalRecordStatus.QUEUED,
            IncrementalRecordStatus.RETRY_WAIT,
            IncrementalRecordStatus.PROCESSING,
        ]
    )
    stmt: Select[tuple[IncrementalRecordState]] = select(IncrementalRecordState).where(
        IncrementalRecordState.connector == connector,
        IncrementalRecordState.scope_id == _normalize_text(scope_id, "scope_id"),
        IncrementalRecordState.parent_type == _normalize_text(parent_type, "parent_type"),
        IncrementalRecordState.parent_id == _normalize_text(parent_id, "parent_id"),
        IncrementalRecordState.generation <= max_generation,
        IncrementalRecordState.status.in_(target_statuses),
    )
    stmt = stmt.order_by(
        IncrementalRecordState.generation.asc(),
        IncrementalRecordState.last_event_at.asc(),
        IncrementalRecordState.updated_at.asc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def _update_record_status(
    db: Session,
    *,
    record_key: str,
    from_statuses: Sequence[IncrementalRecordStatus],
    to_status: IncrementalRecordStatus,
    expected_generation: int | None = None,
    attempt: int | None = None,
    next_retry_at: datetime | None = None,
    queued_generation: int | None = None,
    processing_generation: int | None = None,
    last_synced_at: datetime | None = None,
    last_error: str | None = None,
    lease_owner: str | None = None,
    lease_until: datetime | None = None,
) -> int:
    _validate_record_transition(from_statuses, to_status)

    now = _utc_now()
    values: dict[str, object] = {
        "status": to_status,
        "updated_at": now,
    }
    if attempt is not None:
        values["attempt"] = attempt
    if next_retry_at is not None or to_status != IncrementalRecordStatus.RETRY_WAIT:
        values["next_retry_at"] = _to_utc(next_retry_at) if next_retry_at is not None else None
    if queued_generation is not None or to_status != IncrementalRecordStatus.QUEUED:
        values["queued_generation"] = queued_generation
    if processing_generation is not None or to_status != IncrementalRecordStatus.PROCESSING:
        values["processing_generation"] = processing_generation
    if last_synced_at is not None:
        values["last_synced_at"] = _to_utc(last_synced_at)
    if last_error is not None or to_status in {
        IncrementalRecordStatus.DEBOUNCING,
        IncrementalRecordStatus.QUEUED,
        IncrementalRecordStatus.PROCESSING,
    }:
        values["last_error"] = last_error
    values["lease_owner"] = lease_owner
    values["lease_until"] = _to_utc(lease_until) if lease_until is not None else None

    stmt = update(IncrementalRecordState).where(
        IncrementalRecordState.record_key == _normalize_text(record_key, "record_key"),
        IncrementalRecordState.status.in_(list(from_statuses)),
    )
    if expected_generation is not None:
        stmt = stmt.where(IncrementalRecordState.generation == expected_generation)

    result = db.execute(stmt.values(**values))
    return result.rowcount or 0


def transition_record_status(
    db: Session,
    *,
    record_key: str,
    from_statuses: Sequence[IncrementalRecordStatus],
    to_status: IncrementalRecordStatus,
    expected_generation: int | None = None,
    attempt: int | None = None,
    next_retry_at: datetime | None = None,
    queued_generation: int | None = None,
    processing_generation: int | None = None,
    last_synced_at: datetime | None = None,
    last_error: str | None = None,
    lease_owner: str | None = None,
    lease_until: datetime | None = None,
) -> bool:
    try:
        updated = _update_record_status(
            db,
            record_key=record_key,
            from_statuses=from_statuses,
            to_status=to_status,
            expected_generation=expected_generation,
            attempt=attempt,
            next_retry_at=next_retry_at,
            queued_generation=queued_generation,
            processing_generation=processing_generation,
            last_synced_at=last_synced_at,
            last_error=last_error,
            lease_owner=lease_owner,
            lease_until=lease_until,
        )
        db.commit()
        return updated == 1
    except Exception:
        db.rollback()
        raise


def mark_parent_cohort_synced(
    db: Session,
    *,
    connector: SyncConnector,
    scope_id: str,
    parent_type: str,
    parent_id: str,
    max_generation: int,
    last_synced_at: datetime | None = None,
) -> int:
    synced_at = _to_utc(last_synced_at or _utc_now())
    stmt = (
        update(IncrementalRecordState)
        .where(
            IncrementalRecordState.connector == connector,
            IncrementalRecordState.scope_id == _normalize_text(scope_id, "scope_id"),
            IncrementalRecordState.parent_type == _normalize_text(parent_type, "parent_type"),
            IncrementalRecordState.parent_id == _normalize_text(parent_id, "parent_id"),
            IncrementalRecordState.generation <= max_generation,
            IncrementalRecordState.status.in_(
                [
                    IncrementalRecordStatus.QUEUED,
                    IncrementalRecordStatus.RETRY_WAIT,
                    IncrementalRecordStatus.PROCESSING,
                ]
            ),
        )
        .values(
            status=IncrementalRecordStatus.SYNCED,
            attempt=0,
            next_retry_at=None,
            queued_generation=None,
            processing_generation=None,
            last_synced_at=synced_at,
            last_error=None,
            lease_owner=None,
            lease_until=None,
            updated_at=_utc_now(),
        )
    )
    try:
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
    except Exception:
        db.rollback()
        raise


def get_outbox_entry(db: Session, outbox_id: int) -> IncrementalStreamOutbox | None:
    stmt = select(IncrementalStreamOutbox).where(IncrementalStreamOutbox.id == outbox_id)
    return db.execute(stmt).scalar_one_or_none()


def _find_outbox(
    db: Session,
    *,
    record_key: str,
    generation: int,
) -> IncrementalStreamOutbox | None:
    stmt = select(IncrementalStreamOutbox).where(
        IncrementalStreamOutbox.record_key == _normalize_text(record_key, "record_key"),
        IncrementalStreamOutbox.generation == generation,
    )
    return db.execute(stmt).scalar_one_or_none()


def _upsert_outbox(
    db: Session,
    payload: IncrementalOutboxCreateInput,
) -> int | None:
    now = _utc_now()
    stmt = insert(IncrementalStreamOutbox).values(
        record_key=_normalize_text(payload.record_key, "record_key"),
        generation=payload.generation,
        connector=payload.connector,
        scope_id=_normalize_text(payload.scope_id, "scope_id"),
        parent_type=_normalize_text(payload.parent_type, "parent_type"),
        parent_id=_normalize_text(payload.parent_id, "parent_id"),
        event_kind=_normalize_text(payload.event_kind, "event_kind"),
        status=IncrementalOutboxStatus.PENDING,
        attempt=0,
        stream_message_id=None,
        published_at=None,
        last_error=None,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            IncrementalStreamOutbox.record_key,
            IncrementalStreamOutbox.generation,
        ],
        set_={
            "status": IncrementalOutboxStatus.PENDING,
            "stream_message_id": None,
            "published_at": None,
            "last_error": None,
            "updated_at": now,
        },
    )
    result = db.execute(stmt.returning(IncrementalStreamOutbox.id))
    return result.scalar_one_or_none()


def upsert_outbox_entry(
    db: Session,
    payload: IncrementalOutboxCreateInput,
) -> IncrementalStreamOutbox:
    try:
        outbox_id = _upsert_outbox(db, payload)

        if outbox_id is None:
            entry = _find_outbox(
                db,
                record_key=payload.record_key,
                generation=payload.generation,
            )
            if entry is None:
                raise RuntimeError("failed to create incremental outbox entry")
            db.commit()
            return entry

        entry = get_outbox_entry(db, outbox_id)
        if entry is None:
            raise RuntimeError("failed to load incremental outbox entry")

        db.commit()
        return entry
    except Exception:
        db.rollback()
        raise


def promote_record(
    db: Session,
    *,
    record: IncrementalRecordState,
) -> bool:
    from_status = (
        IncrementalRecordStatus.RETRY_WAIT
        if record.status == IncrementalRecordStatus.RETRY_WAIT
        else IncrementalRecordStatus.DEBOUNCING
    )

    try:
        updated = _update_record_status(
            db,
            record_key=record.record_key,
            from_statuses=[from_status],
            to_status=IncrementalRecordStatus.QUEUED,
            expected_generation=record.generation,
            queued_generation=record.generation,
        )
        if updated != 1:
            db.rollback()
            return False

        outbox_id = _upsert_outbox(
            db,
            IncrementalOutboxCreateInput(
                record_key=record.record_key,
                generation=record.generation,
                connector=record.connector,
                scope_id=record.scope_id,
                parent_type=record.parent_type,
                parent_id=record.parent_id,
                event_kind=record.event_kind,
            ),
        )
        if outbox_id is None:
            entry = _find_outbox(
                db,
                record_key=record.record_key,
                generation=record.generation,
            )
            if entry is None:
                raise RuntimeError("failed to create incremental outbox entry")

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def list_pending_outbox_entries(
    db: Session,
    *,
    connector: SyncConnector | None = None,
    statuses: Sequence[IncrementalOutboxStatus] | None = None,
    limit: int = 100,
) -> list[IncrementalStreamOutbox]:
    target_statuses = list(statuses or [IncrementalOutboxStatus.PENDING])
    stmt: Select[tuple[IncrementalStreamOutbox]] = select(IncrementalStreamOutbox).where(
        IncrementalStreamOutbox.status.in_(target_statuses)
    )
    if connector is not None:
        stmt = stmt.where(IncrementalStreamOutbox.connector == connector)

    stmt = stmt.order_by(
        IncrementalStreamOutbox.created_at.asc(),
        IncrementalStreamOutbox.id.asc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def _transition_outbox_status(
    db: Session,
    *,
    outbox_id: int,
    from_statuses: Sequence[IncrementalOutboxStatus],
    to_status: IncrementalOutboxStatus,
    stream_message_id: str | None = None,
    last_error: str | None = None,
    increment_attempt: bool = False,
) -> int:
    _validate_outbox_transition(from_statuses, to_status)

    now = _utc_now()
    values: dict[str, object] = {
        "status": to_status,
        "updated_at": now,
        "stream_message_id": stream_message_id,
        "last_error": last_error,
    }
    if to_status == IncrementalOutboxStatus.PUBLISHED:
        values["published_at"] = now
    if to_status != IncrementalOutboxStatus.PUBLISHED:
        values["published_at"] = None
    if increment_attempt:
        values["attempt"] = IncrementalStreamOutbox.attempt + 1

    stmt = (
        update(IncrementalStreamOutbox)
        .where(
            IncrementalStreamOutbox.id == outbox_id,
            IncrementalStreamOutbox.status.in_(list(from_statuses)),
        )
        .values(**values)
    )
    result = db.execute(stmt)
    return result.rowcount or 0


def transition_outbox_status(
    db: Session,
    *,
    outbox_id: int,
    from_statuses: Sequence[IncrementalOutboxStatus],
    to_status: IncrementalOutboxStatus,
    stream_message_id: str | None = None,
    last_error: str | None = None,
    increment_attempt: bool = False,
) -> bool:
    try:
        updated = _transition_outbox_status(
            db,
            outbox_id=outbox_id,
            from_statuses=from_statuses,
            to_status=to_status,
            stream_message_id=stream_message_id,
            last_error=last_error,
            increment_attempt=increment_attempt,
        )
        db.commit()
        return updated == 1
    except Exception:
        db.rollback()
        raise


def claim_outbox_for_publish(db: Session, *, outbox_id: int) -> bool:
    return transition_outbox_status(
        db,
        outbox_id=outbox_id,
        from_statuses=[IncrementalOutboxStatus.PENDING, IncrementalOutboxStatus.FAILED],
        to_status=IncrementalOutboxStatus.PUBLISHING,
        stream_message_id=None,
        last_error=None,
        increment_attempt=True,
    )


def complete_outbox_publish(
    db: Session,
    *,
    outbox_id: int,
    stream_message_id: str,
    last_error: str | None = None,
) -> bool:
    return transition_outbox_status(
        db,
        outbox_id=outbox_id,
        from_statuses=[IncrementalOutboxStatus.PUBLISHING],
        to_status=IncrementalOutboxStatus.PUBLISHED,
        stream_message_id=stream_message_id,
        last_error=last_error,
    )


def complete_outbox_skip(
    db: Session,
    *,
    outbox_id: int,
    last_error: str | None = None,
) -> bool:
    return transition_outbox_status(
        db,
        outbox_id=outbox_id,
        from_statuses=[IncrementalOutboxStatus.PUBLISHING],
        to_status=IncrementalOutboxStatus.SKIPPED,
        stream_message_id=None,
        last_error=last_error,
    )


def fail_outbox_publish(
    db: Session,
    *,
    outbox_id: int,
    last_error: str | None,
) -> bool:
    return transition_outbox_status(
        db,
        outbox_id=outbox_id,
        from_statuses=[IncrementalOutboxStatus.PUBLISHING],
        to_status=IncrementalOutboxStatus.FAILED,
        stream_message_id=None,
        last_error=last_error,
    )


def recover_stale_outbox_claims(
    db: Session,
    *,
    stale_seconds: int,
    connector: SyncConnector | None = None,
    limit: int = 100,
) -> int:
    stale_before = _utc_now() - timedelta(seconds=max(1, stale_seconds))
    ids_stmt = select(IncrementalStreamOutbox.id).where(
        IncrementalStreamOutbox.status == IncrementalOutboxStatus.PUBLISHING,
        IncrementalStreamOutbox.updated_at <= stale_before,
    )
    if connector is not None:
        ids_stmt = ids_stmt.where(IncrementalStreamOutbox.connector == connector)

    ids_stmt = ids_stmt.order_by(
        IncrementalStreamOutbox.updated_at.asc(),
        IncrementalStreamOutbox.id.asc(),
    ).limit(limit)
    outbox_ids = list(db.execute(ids_stmt).scalars().all())
    if not outbox_ids:
        return 0

    stmt = (
        update(IncrementalStreamOutbox)
        .where(IncrementalStreamOutbox.id.in_(outbox_ids))
        .values(
            status=IncrementalOutboxStatus.FAILED,
            stream_message_id=None,
            last_error="stale_publishing_timeout",
            updated_at=_utc_now(),
            published_at=None,
        )
    )
    try:
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
    except Exception:
        db.rollback()
        raise


def recover_stale_processing_records(
    db: Session,
    *,
    stale_seconds: int,
    connector: SyncConnector | None = None,
    limit: int = 100,
) -> int:
    stale_before = _utc_now() - timedelta(seconds=max(1, stale_seconds))
    ids_stmt = select(IncrementalRecordState.record_key).where(
        IncrementalRecordState.status == IncrementalRecordStatus.PROCESSING,
        IncrementalRecordState.lease_until.is_not(None),
        IncrementalRecordState.lease_until <= stale_before,
    )
    if connector is not None:
        ids_stmt = ids_stmt.where(IncrementalRecordState.connector == connector)

    ids_stmt = ids_stmt.order_by(
        IncrementalRecordState.lease_until.asc(),
        IncrementalRecordState.updated_at.asc(),
    ).limit(limit)
    record_keys = list(db.execute(ids_stmt).scalars().all())
    if not record_keys:
        return 0

    stmt = (
        update(IncrementalRecordState)
        .where(IncrementalRecordState.record_key.in_(record_keys))
        .values(
            status=IncrementalRecordStatus.RETRY_WAIT,
            next_retry_at=_utc_now(),
            processing_generation=None,
            lease_owner=None,
            lease_until=None,
            last_error="stale_processing_timeout",
            updated_at=_utc_now(),
        )
    )
    try:
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
    except Exception:
        db.rollback()
        raise
