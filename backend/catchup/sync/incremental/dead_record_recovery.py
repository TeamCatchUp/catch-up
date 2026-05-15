from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.models import IncrementalRecordState
from catchup.db.models import IncrementalRecordStatus

logger = structlog.get_logger(__name__)

_DEFAULT_DEAD_RECORD_RECOVERY_BATCH_SIZE = 1000


@dataclass(slots=True)
class IncrementalDeadRecordRecoveryResult:
    scanned: int = 0
    requeued: int = 0

    def to_log_fields(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_log_fields(), ensure_ascii=False, sort_keys=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _requeue_dead_record(
    db: Session,
    *,
    record: IncrementalRecordState,
    max_attempts: int,
    recovered_at: datetime,
) -> int:
    # promoter가 다시 QUEUED로 올릴 수 있도록 DEAD record를 DEBOUNCING으로 되돌린다.
    # attempt는 유지, 복구 후 다시 실패하면 attempt가 max_attempts보다 커져 다음 cycle에서 제외
    stmt = (
        update(IncrementalRecordState)
        .where(
            IncrementalRecordState.record_key == record.record_key,
            IncrementalRecordState.status == IncrementalRecordStatus.DEAD,
            IncrementalRecordState.generation == record.generation,
            IncrementalRecordState.attempt >= 1,
            IncrementalRecordState.attempt <= max_attempts,
        )
        .values(
            status=IncrementalRecordStatus.DEBOUNCING,
            debounce_until=recovered_at,
            next_retry_at=None,
            queued_generation=None,
            processing_generation=None,
            last_error=None,
            lease_owner=None,
            lease_until=None,
            updated_at=recovered_at,
        )
    )
    result = db.execute(stmt)
    return result.rowcount or 0


def recover_exhausted_dead_incremental_records(
    db: Session,
    *,
    max_attempts: int,
    limit: int = _DEFAULT_DEAD_RECORD_RECOVERY_BATCH_SIZE,
    now: datetime | None = None,
) -> IncrementalDeadRecordRecoveryResult:
    recovered_at = _to_utc(now or _utc_now())
    max_recoverable_attempt = max(1, int(max_attempts))
    batch_limit = max(1, int(limit))

    # 추가 이벤트로 이미 다시 sync 흐름에 탄 record는 status가 DEAD가 아니므로 제외됨
    records = list(
        db.execute(
            select(IncrementalRecordState)
            .where(
                IncrementalRecordState.status == IncrementalRecordStatus.DEAD,
                IncrementalRecordState.attempt >= 1,
                IncrementalRecordState.attempt <= max_recoverable_attempt,
            )
            .order_by(
                IncrementalRecordState.updated_at.asc(),
                IncrementalRecordState.record_key.asc(),
            )
            .limit(batch_limit)
        )
        .scalars()
        .all()
    )

    result = IncrementalDeadRecordRecoveryResult(scanned=len(records))

    # 아직 max attempts를 넘지 않은 DEAD record만 회복
    for record in records:
        updated = _requeue_dead_record(
            db,
            record=record,
            max_attempts=max_recoverable_attempt,
            recovered_at=recovered_at,
        )
        if updated:
            result.requeued += 1

    db.commit()
    return result


def _recover_exhausted_dead_records_with_session(
    *,
    limit: int | None,
    now: datetime | None,
) -> IncrementalDeadRecordRecoveryResult:
    with SessionLocal() as db:
        try:
            return recover_exhausted_dead_incremental_records(
                db,
                max_attempts=settings.INCREMENTAL_MAX_ATTEMPTS,
                limit=limit or _DEFAULT_DEAD_RECORD_RECOVERY_BATCH_SIZE,
                now=now,
            )
        except Exception:
            db.rollback()
            raise


# TODO : 관측성 페이지 추가 이후 DLQ는 수동 복구로 변경
async def recover_incremental_dead_records(
    *,
    limit: int | None = None,
    now: datetime | None = None,
) -> IncrementalDeadRecordRecoveryResult:
    result = await run_in_threadpool(
        _recover_exhausted_dead_records_with_session,
        limit=limit,
        now=now,
    )
    logger.info(
        "incremental_dead_record_recovery_completed",
        **result.to_log_fields(),
    )
    return result
