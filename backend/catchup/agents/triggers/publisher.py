from __future__ import annotations

import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from catchup.agents.triggers.stream import AGENT_RUN_REQUEST_STREAM_KEY
from catchup.agents.triggers.stream import AgentRunRequest
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerOutboxStatus
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus
from catchup.utils.redis import create_sync_redis_client

logger = structlog.get_logger(__name__)

DEBOUNCE_TTL_KEY_PREFIX = "agent_trigger:debounce:"


def publish_pending_agent_trigger_outbox(
    db: Session,
    *,
    limit: int = 20,
    stale_publishing_after: timedelta = timedelta(minutes=5),
) -> int:
    """재시도 가능한 outbox만 claim/publish 경계로 넘긴다."""
    outboxes = list(
        db.scalars(
            select(AgentTriggerOutbox)
            .where(_retryable_outbox_condition(stale_publishing_after))
            .order_by(AgentTriggerOutbox.created_at.asc(), AgentTriggerOutbox.id.asc())
            .limit(limit)
        ).all()
    )
    published = 0
    for outbox in outboxes:
        if publish_agent_trigger_outbox(db=db, outbox_id=outbox.id):
            published += 1
    return published


def publish_agent_trigger_outbox(
    db: Session,
    outbox_id: int,
    *,
    stale_publishing_after: timedelta = timedelta(minutes=5),
) -> bool:
    """outbox 한 건을 Redis Stream message로 발행하고 run을 dispatching으로 claim한다.

    DB 상태 전이를 먼저 commit한 뒤 Redis에 발행해야 worker가 메시지를 받아도
    run ledger를 기준으로 idempotency를 판단할 수 있다.
    """
    outbox = _claim_outbox_for_publish(
        db=db,
        outbox_id=outbox_id,
        stale_publishing_after=stale_publishing_after,
    )
    if outbox is None:
        return False
    run = db.get(AgentTriggerRun, outbox.run_id)
    if run is None:
        _fail_outbox(db=db, outbox=outbox, error="run_not_found")
        return False
    if not _claim_run_for_request(db=db, run=run):
        _fail_outbox(db=db, outbox=outbox, error="run_claim_failed")
        return False

    db.commit()
    request = AgentRunRequest(
        run_id=outbox.run_id,
        trigger_id=outbox.trigger_id,
        agent_spec_id=outbox.agent_spec_id,
        event_id=outbox.event_id,
        policy_kind=run.policy_kind,
        dispatch_token=str(run.dispatch_token),
    )
    try:
        message_id = _publish_request_sync(request)
    except Exception as exc:
        db.rollback()
        outbox = db.get(AgentTriggerOutbox, outbox_id)
        if outbox is None:
            return False
        _fail_outbox(db=db, outbox=outbox, error=str(exc))
        return False

    outbox = db.get(AgentTriggerOutbox, outbox_id)
    if outbox is None:
        return False
    outbox.status = AgentTriggerOutboxStatus.PUBLISHED
    outbox.stream_message_id = message_id
    outbox.published_at = datetime.now(timezone.utc)
    outbox.last_error = None
    db.commit()
    return True


def schedule_debounce_wakeup(run: AgentTriggerRun) -> None:
    """
    Redis TTL을 이용하여 Debounce Wakeup을 예약
    """
    if run.run_after is None or run.entity_key is None:
        return
    seconds = max(1, int((run.run_after - datetime.now(timezone.utc)).total_seconds()))
    payload = {
        "run_id": run.id,
        "trigger_id": run.trigger_id,
        "entity_key": run.entity_key,
        "dispatch_token": str(run.dispatch_token),
    }
    try:
        _set_debounce_ttl_sync(
            key=debounce_ttl_key(
                run_id=run.id,
                dispatch_token=str(run.dispatch_token),
            ),
            value=json.dumps(payload, separators=(",", ":")),
            seconds=seconds,
        )
    except Exception as exc:
        logger.warning(
            "agent_trigger_debounce_ttl_set_failed",
            run_id=run.id,
            trigger_id=run.trigger_id,
            error=str(exc),
        )


def debounce_ttl_key(*, run_id: int, dispatch_token: str) -> str:
    """stale TTL 알림을 DB token 검증으로 거르기 위한 key 형식."""
    return f"{DEBOUNCE_TTL_KEY_PREFIX}{run_id}:{dispatch_token}"


def _publish_request_sync(request: AgentRunRequest) -> str:
    """Redis Stream 발행 결과를 listener가 저장할 문자열 message id로 정규화한다."""
    redis = create_sync_redis_client(client_type="agent_trigger_publisher")
    try:
        message_id = redis.xadd(
            AGENT_RUN_REQUEST_STREAM_KEY,
            request.to_stream_fields(),
        )
    finally:
        redis.close()
    if isinstance(message_id, bytes):
        return message_id.decode("utf-8")
    return str(message_id)


def _set_debounce_ttl_sync(*, key: str, value: str, seconds: int) -> None:
    """debounce wakeup용 TTL key를 Redis에 쓴다."""
    redis = create_sync_redis_client(client_type="agent_trigger_debounce_ttl")
    try:
        redis.set(key, value, ex=seconds)
    finally:
        redis.close()


def _claim_outbox_for_publish(
    *,
    db: Session,
    outbox_id: int,
    stale_publishing_after: timedelta,
) -> AgentTriggerOutbox | None:
    """여러 publisher/recovery가 같은 outbox를 중복 발행하지 않도록 claim한다."""
    result = db.execute(
        update(AgentTriggerOutbox)
        .where(
            AgentTriggerOutbox.id == outbox_id,
            _retryable_outbox_condition(stale_publishing_after),
        )
        .values(
            status=AgentTriggerOutboxStatus.PUBLISHING,
            updated_at=datetime.now(timezone.utc),
        )
        .returning(AgentTriggerOutbox.id)
    )
    claimed_id = result.scalar_one_or_none()
    if claimed_id is None:
        db.rollback()
        return None
    db.flush()
    return db.get(AgentTriggerOutbox, claimed_id)


def _retryable_outbox_condition(stale_publishing_after: timedelta) -> ColumnElement[bool]:
    """pending/failed와 오래 멈춘 publishing 상태만 재발행 대상으로 본다."""
    return or_(
        AgentTriggerOutbox.status.in_(
            [
                AgentTriggerOutboxStatus.PENDING,
                AgentTriggerOutboxStatus.FAILED,
            ]
        ),
        (
            (AgentTriggerOutbox.status == AgentTriggerOutboxStatus.PUBLISHING)
            & (
                AgentTriggerOutbox.updated_at
                <= datetime.now(timezone.utc) - stale_publishing_after
            )
        ),
    )


def _claim_run_for_request(*, db: Session, run: AgentTriggerRun) -> bool:
    """worker에게 넘길 수 있는 run만 dispatching 상태로 전환한다."""
    if run.status == AgentTriggerRunStatus.DISPATCHING:
        db.flush()
        return True
    now = datetime.now(timezone.utc)
    conditions = [
        AgentTriggerRun.id == run.id,
        AgentTriggerRun.status == AgentTriggerRunStatus.PENDING,
    ]
    if run.policy_kind == "debounce":
        conditions.append(AgentTriggerRun.run_after <= now)
    result = db.execute(
        update(AgentTriggerRun)
        .where(*conditions)
        .values(
            status=AgentTriggerRunStatus.DISPATCHING,
            updated_at=now,
        )
        .returning(AgentTriggerRun.id)
    )
    claimed = result.scalar_one_or_none() is not None
    if claimed:
        db.flush()
    else:
        db.rollback()
    return claimed


def _fail_outbox(*, db: Session, outbox: AgentTriggerOutbox, error: str) -> None:
    """발행 실패를 outbox에 남겨 recovery job이 같은 경계에서 재시도하게 한다."""
    outbox.status = AgentTriggerOutboxStatus.FAILED
    outbox.last_error = error
    db.commit()
