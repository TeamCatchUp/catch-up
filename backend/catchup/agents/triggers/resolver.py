from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from catchup.agents.triggers.evaluator import TriggerWhereEvaluationError
from catchup.agents.triggers.evaluator import evaluate_where_clause
from catchup.agents.triggers.evaluator import extract_path
from catchup.agents.triggers.events import AgentTriggerMatch
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.events import normalize_verified_connector_event
from catchup.agents.triggers.policies import DebouncePolicy
from catchup.agents.triggers.policies import ImmediatePolicy
from catchup.agents.triggers.policies import PolicyValidationError
from catchup.agents.triggers.policies import parse_policy
from catchup.agents.triggers.publisher import publish_pending_agent_trigger_outbox
from catchup.agents.triggers.publisher import schedule_debounce_wakeup
from catchup.connector_core.domain.webhooks import VerifiedConnectorWebhookEvent
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_PRIMARY
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_RESET
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_START
from catchup.db.agent_triggers import get_trigger_event_subscription_candidates
from catchup.db.engine import SessionLocal
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class AgentTriggerIngressResult:
    """웹훅 ingress 처리 결과를 API 계층에 전달하는 값 객체."""

    status: str
    reason: str | None = None
    run_ids: list[int] | None = None
    matched_count: int = 0


def handle_verified_webhook_event(
    verified_event: VerifiedConnectorWebhookEvent,
) -> AgentTriggerIngressResult:
    """
    Router에서 AgentTrigger의 진입점
    """
    db = SessionLocal()
    try:
        normalized = normalize_verified_connector_event(verified_event)
        if normalized.event is None:
            return AgentTriggerIngressResult(
                status="ignored",
                reason=normalized.ignored_reason or "normalization_failed",
            )
        return handle_agent_webhook_event(db=db, event=normalized.event)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_agent_webhook_event(
    db: Session,
    event: AgentWebhookEvent,
) -> AgentTriggerIngressResult:
    """
    정규화된 webhook event를 run/outbox로 저장하고 worker wakeup을 연결한다.

    매칭, run 영속화, wakeup 예약 순서가 ingress의 장애 경계다.
    한 trigger의 idempotency 충돌은 savepoint로 흡수하지만, DB 자체 실패는 호출자에게 전파해 webhook retry가 가능하게 둔다.
    """
    matches = resolve_trigger_matches(db=db, event=event)
    if not matches:
        return AgentTriggerIngressResult(status="ignored", reason="no_matching_trigger")

    run_ids: list[int] = []
    debounce_runs: list[AgentTriggerRun] = []
    for match in matches:
        try:
            # 각 match를 savepoint로 감싸 한 trigger의 중복 충돌이 전체 이벤트를 깨지 않게 한다.
            with db.begin_nested():
                if match.policy_kind == "immediate":
                    run = _persist_immediate_match(db=db, match=match)
                else:
                    run = _persist_debounce_match(db=db, match=match)
        except IntegrityError:
            if match.policy_kind == "immediate":
                run = _load_immediate_run(db=db, match=match)
            else:
                run = _load_active_debounce_run(db=db, match=match)
        if run is None:
            continue
        run_ids.append(run.id)
        if (
            match.policy_kind == "debounce"
            and run.status == AgentTriggerRunStatus.PENDING
        ):
            debounce_runs.append(run)
    if not run_ids:
        db.rollback()
        return AgentTriggerIngressResult(
            status="ignored",
            reason="no_persisted_trigger_run",
            matched_count=len(matches),
        )
    db.commit()
    for run in debounce_runs:
        schedule_debounce_wakeup(run)

    try:
        # Redis publish 실패는 outbox에 남겨 recovery/retry 경로가 처리하게 둔다.
        publish_pending_agent_trigger_outbox(db=db)
    except Exception as exc:
        logger.warning(
            "agent_trigger_outbox_publish_deferred",
            event_id=event.event_id,
            error=str(exc),
        )
    return AgentTriggerIngressResult(
        status="accepted",
        run_ids=run_ids,
        matched_count=len(matches),
    )


def resolve_trigger_matches(db: Session, event: AgentWebhookEvent) -> list[AgentTriggerMatch]:
    matches: list[AgentTriggerMatch] = []
    candidates = get_trigger_event_subscription_candidates(
        db,
        source=event.source,
        event_type=event.event_type,
    )

    for candidate in candidates:
        trigger = candidate.trigger

        if not _trigger_can_handle_event(
            trigger=trigger,
            event=event,
            roles=candidate.roles,
        ):
            continue

        try:
            policy = parse_policy(trigger.condition)
        except PolicyValidationError as exc:
            logger.warning(
                "invalid_trigger_policy_ignored",
                trigger_id=trigger.id,
                event_id=event.event_id,
                reason=str(exc),
            )
            continue

        try:
            if isinstance(policy, ImmediatePolicy):
                match = _match_immediate_policy(
                    trigger=trigger,
                    policy=policy,
                    event=event,
                    roles=candidate.roles,
                )
            else:
                match = _match_debounce_policy(
                    trigger=trigger,
                    policy=policy,
                    event=event,
                    roles=candidate.roles,
                )
        except TriggerWhereEvaluationError as exc:
            logger.warning(
                "trigger_policy_where_ignored",
                trigger_id=trigger.id,
                event_id=event.event_id,
                reason=str(exc),
            )
            continue
        if match is not None:
            matches.append(match)
    return matches


def _match_immediate_policy(
    *,
    trigger: Any,
    policy: ImmediatePolicy,
    event: AgentWebhookEvent,
    roles: frozenset[str],
) -> AgentTriggerMatch | None:
    if TRIGGER_EVENT_ROLE_PRIMARY not in roles:
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="immediate trigger requires primary subscription role",
        )
        return None
    if not (
        trigger.event_type == event.event_type
        and evaluate_where_clause(policy.where, event)
    ):
        return None
    return AgentTriggerMatch(
        trigger_id=trigger.id,
        agent_spec_id=trigger.agent_spec_id,
        event=event,
        policy_kind=policy.kind,
        policy=policy.model_dump(mode="json"),
    )


def _match_debounce_policy(
    *,
    trigger: Any,
    policy: DebouncePolicy,
    event: AgentWebhookEvent,
    roles: frozenset[str],
) -> AgentTriggerMatch | None:
    is_start = (
        TRIGGER_EVENT_ROLE_START in roles and event.event_type == policy.start_event_type
    )
    is_reset = (
        TRIGGER_EVENT_ROLE_RESET in roles and event.event_type in policy.reset_event_types
    )
    if TRIGGER_EVENT_ROLE_START in roles and event.event_type != policy.start_event_type:
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="start subscription event_type differs from policy.start_event_type",
        )
    if (
        TRIGGER_EVENT_ROLE_RESET in roles
        and event.event_type not in policy.reset_event_types
    ):
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="reset subscription event_type is absent from policy.reset_event_types",
        )

    if is_start and evaluate_where_clause(policy.where, event):
        entity_key = _canonical_entity_key(extract_path(event, policy.entity_key_path))
        if entity_key:
            return AgentTriggerMatch(
                trigger_id=trigger.id,
                agent_spec_id=trigger.agent_spec_id,
                event=event,
                policy_kind=policy.kind,
                policy=policy.model_dump(mode="json"),
                entity_key=entity_key,
                reset=False,
            )
    elif is_reset and evaluate_where_clause(policy.reset_where, event):
        # reset은 새 run을 만들지 않고 같은 entity의 pending debounce만 갱신/취소한다.
        entity_key = _canonical_entity_key(
            extract_path(event, policy.reset_entity_key_path)
        )
        if entity_key:
            return AgentTriggerMatch(
                trigger_id=trigger.id,
                agent_spec_id=trigger.agent_spec_id,
                event=event,
                policy_kind=policy.kind,
                policy=policy.model_dump(mode="json"),
                entity_key=entity_key,
                reset=True,
            )
    return None


def _trigger_can_handle_event(
    *,
    trigger: Any,
    event: AgentWebhookEvent,
    roles: frozenset[str],
) -> bool:
    if getattr(trigger, "type", None) != "webhook":
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="subscription candidate is not a webhook trigger",
        )
        return False
    if getattr(trigger, "source", None) != event.source:
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="subscription candidate source differs from event source",
        )
        return False

    agent_spec = getattr(trigger, "agent_spec", None)
    if agent_spec is None:
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="subscription candidate has no loaded agent spec",
        )
        return False
    if getattr(agent_spec, "status", None) != AgentStatus.ACTIVE:
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="agent spec is not active",
        )
        return False
    if getattr(agent_spec, "workspace_id", None) != getattr(trigger, "workspace_id", None):
        _log_subscription_candidate_skip(
            trigger_id=trigger.id,
            event=event,
            roles=roles,
            reason="agent spec workspace differs from trigger workspace",
        )
        return False
    return True


def _log_subscription_candidate_skip(
    *,
    trigger_id: int,
    event: AgentWebhookEvent,
    roles: frozenset[str],
    reason: str,
) -> None:
    logger.warning(
        "agent_trigger_subscription_candidate_skipped",
        trigger_id=trigger_id,
        event_id=event.event_id,
        event_type=event.event_type,
        roles=sorted(roles),
        reason=reason,
    )


def _persist_immediate_match(db: Session, match: AgentTriggerMatch) -> AgentTriggerRun:
    existing = _load_immediate_run(db=db, match=match)
    if existing is not None:
        return existing

    run = AgentTriggerRun(
        trigger_id=match.trigger_id,
        policy_kind=match.policy_kind,
        entity_key=match.entity_key,
        status=AgentTriggerRunStatus.PENDING,
        run_after=None,
        start_event_id=match.event.event_id,
        latest_event_id=match.event.event_id,
        dispatch_token=uuid.uuid4(),
        policy_metadata=_policy_metadata(match=match),
    )
    db.add(run)
    db.flush()
    db.add(
        AgentTriggerOutbox(
            run_id=run.id,
            trigger_id=match.trigger_id,
            agent_spec_id=match.agent_spec_id,
            event_id=match.event.event_id,
        )
    )
    db.flush()
    return run


def _persist_debounce_match(db: Session, match: AgentTriggerMatch) -> AgentTriggerRun | None:
    policy = DebouncePolicy.model_validate(match.policy)
    now = datetime.now(timezone.utc)
    run_after = now + timedelta(seconds=policy.quiet_period_seconds)
    existing_id = db.scalar(
        update(AgentTriggerRun)
        .where(
            AgentTriggerRun.trigger_id == match.trigger_id,
            AgentTriggerRun.entity_key == match.entity_key,
            AgentTriggerRun.status == AgentTriggerRunStatus.PENDING,
        )
        .values(
            latest_event_id=match.event.event_id,
            run_after=run_after,
            dispatch_token=uuid.uuid4(),
            policy_metadata=_policy_metadata(match=match),
            updated_at=now,
        )
        .returning(AgentTriggerRun.id)
    )
    if existing_id is not None:
        db.flush()
        return db.get(AgentTriggerRun, existing_id)
    active_run = _load_active_debounce_run(db=db, match=match)
    if active_run is not None:
        return active_run
    if match.reset:
        return None

    run = AgentTriggerRun(
        trigger_id=match.trigger_id,
        policy_kind=match.policy_kind,
        entity_key=match.entity_key,
        status=AgentTriggerRunStatus.PENDING,
        run_after=run_after,
        start_event_id=match.event.event_id,
        latest_event_id=match.event.event_id,
        dispatch_token=uuid.uuid4(),
        policy_metadata=_policy_metadata(match=match),
    )
    db.add(run)
    db.flush()
    return run


def _load_immediate_run(
    *,
    db: Session,
    match: AgentTriggerMatch,
) -> AgentTriggerRun | None:
    """Immediate 중복 이벤트 재처리를 막기 위한 기존 run 조회"""
    return db.scalar(
        select(AgentTriggerRun).where(
            AgentTriggerRun.trigger_id == match.trigger_id,
            AgentTriggerRun.latest_event_id == match.event.event_id,
            AgentTriggerRun.policy_kind == "immediate",
        )
    )


def _load_active_debounce_run(
    *,
    db: Session,
    match: AgentTriggerMatch,
) -> AgentTriggerRun | None:
    """같은 entity의 예약/실행 중 debounce run을 idempotency 기준으로 재사용"""
    if not match.entity_key:
        return None
    return db.scalar(
        select(AgentTriggerRun).where(
            AgentTriggerRun.trigger_id == match.trigger_id,
            AgentTriggerRun.entity_key == match.entity_key,
            AgentTriggerRun.status.in_(
                [
                    AgentTriggerRunStatus.PENDING,
                    AgentTriggerRunStatus.DISPATCHING,
                ]
            ),
        )
    )


def _policy_metadata(match: AgentTriggerMatch) -> dict[str, Any]:
    return {
        "policy": match.policy,
        "latest_event": match.event.model_dump(mode="json"),
        "matched_at": match.matched_at.isoformat(),
        "reset": match.reset,
    }


def _canonical_entity_key(value: Any) -> str:
    return str(value or "").strip()
