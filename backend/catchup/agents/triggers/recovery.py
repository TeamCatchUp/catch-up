from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from catchup.agents.triggers.publisher import DEBOUNCE_TTL_KEY_PREFIX
from catchup.agents.triggers.publisher import publish_pending_agent_trigger_outbox
from catchup.db.engine import SessionLocal
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus
from catchup.utils.redis import get_redis_client

logger = structlog.get_logger(__name__)


def dispatch_due_debounce_run(
    *,
    db: Session,
    run_id: int,
    dispatch_token: str | None = None,
) -> bool:
    """만료된 debounce run만 outbox로 승격한다.

    Redis TTL과 DB recovery가 같은 함수를 쓰도록 두어 stale token, run_after,
    status 조건을 한곳에서 검증한다.
    """
    run = db.get(AgentTriggerRun, run_id)
    if run is None or run.policy_kind != "debounce":
        return False
    if dispatch_token and str(run.dispatch_token) != dispatch_token:
        return False
    now = datetime.now(timezone.utc)
    if run.run_after is None or run.run_after > now:
        return False

    result = db.execute(
        update(AgentTriggerRun)
        .where(
            AgentTriggerRun.id == run.id,
            AgentTriggerRun.status == AgentTriggerRunStatus.PENDING,
            AgentTriggerRun.run_after <= now,
        )
        .values(
            status=AgentTriggerRunStatus.DISPATCHING,
            updated_at=now,
        )
        .returning(AgentTriggerRun.id)
    )
    if result.scalar_one_or_none() is None:
        db.rollback()
        return False

    trigger = db.get(AgentTrigger, run.trigger_id)
    if trigger is None:
        db.rollback()
        return False
    existing_outbox = db.scalar(
        select(AgentTriggerOutbox).where(AgentTriggerOutbox.run_id == run.id)
    )
    if existing_outbox is None:
        db.add(
            AgentTriggerOutbox(
                run_id=run.id,
                trigger_id=run.trigger_id,
                agent_spec_id=trigger.agent_spec_id,
                event_id=run.latest_event_id,
            )
        )
    db.commit()
    try:
        publish_pending_agent_trigger_outbox(db=db)
    except Exception as exc:
        logger.warning(
            "agent_trigger_debounce_publish_deferred",
            run_id=run.id,
            error=str(exc),
        )
    return True


async def run_debounce_ttl_listener_forever(stop_event: asyncio.Event) -> None:
    """Redis keyspace 알림을 durable DB dispatch 조건으로 다시 확인한다."""
    redis = await get_redis_client()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("__keyevent@*__:expired")
    try:
        while not stop_event.is_set():
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if not message:
                continue
            key = message.get("data")
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            if not isinstance(key, str) or not key.startswith(DEBOUNCE_TTL_KEY_PREFIX):
                continue
            parsed = _parse_debounce_ttl_key(key)
            if parsed is None:
                continue
            run_id, dispatch_token = parsed
            with SessionLocal() as db:
                dispatch_due_debounce_run(
                    db=db,
                    run_id=run_id,
                    dispatch_token=dispatch_token,
                )
    finally:
        await pubsub.close()


def scan_and_dispatch_due_debounce_runs(*, db: Session, limit: int = 100) -> int:
    """Redis 알림 누락을 보완하기 위해 DB에서 만료된 pending debounce를 찾는다."""
    runs = list(
        db.scalars(
            select(AgentTriggerRun)
            .where(
                AgentTriggerRun.status == AgentTriggerRunStatus.PENDING,
                AgentTriggerRun.policy_kind == "debounce",
                AgentTriggerRun.run_after <= datetime.now(timezone.utc),
            )
            .order_by(AgentTriggerRun.run_after.asc(), AgentTriggerRun.id.asc())
            .limit(limit)
        ).all()
    )
    dispatched = 0
    for run in runs:
        if dispatch_due_debounce_run(
            db=db,
            run_id=run.id,
            dispatch_token=str(run.dispatch_token),
        ):
            dispatched += 1
    return dispatched


def recover_stale_agent_trigger_executions(
    *,
    db: Session,
    stale_after: timedelta = timedelta(hours=6),
) -> int:
    """worker가 시작 후 멈춘 run을 실패로 닫아 운영자가 재시도 경계를 볼 수 있게 한다."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(AgentTriggerRun)
        .where(
            AgentTriggerRun.status == AgentTriggerRunStatus.DISPATCHING,
            AgentTriggerRun.execution_started_at.is_not(None),
            AgentTriggerRun.execution_started_at <= now - stale_after,
        )
        .values(
            status=AgentTriggerRunStatus.FAILED,
            last_error="agent_trigger_execution_stale",
            updated_at=now,
        )
    )
    db.commit()
    return int(result.rowcount or 0)


def _parse_debounce_ttl_key(key: str) -> tuple[int, str] | None:
    """Redis keyspace 알림의 문자열 key에서 DB 검증에 필요한 token을 복원한다."""
    if not key.startswith(DEBOUNCE_TTL_KEY_PREFIX):
        return None
    suffix = key[len(DEBOUNCE_TTL_KEY_PREFIX) :]
    run_id_text, separator, dispatch_token = suffix.partition(":")
    if not separator or not dispatch_token:
        return None
    try:
        run_id = int(run_id_text)
    except ValueError:
        return None
    return run_id, dispatch_token
