from dataclasses import dataclass
from typing import Annotated
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import StringConstraints
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from catchup.agents.triggers.policies import DebouncePolicy
from catchup.agents.triggers.policies import ImmediatePolicy
from catchup.agents.triggers.policies import parse_policy
from catchup.db.models import AgentSpec
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerEventSubscription

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TRIGGER_EVENT_ROLE_PRIMARY = "primary"
TRIGGER_EVENT_ROLE_START = "start"
TRIGGER_EVENT_ROLE_RESET = "reset"


class AgentTriggerDefinitionError(ValueError):
    """Agent Trigger 정의가 유효하지 않을 때 발생"""


class AgentTriggerDefinition(BaseModel):
    """Agent Trigger Upsert RequestDTO"""

    model_config = ConfigDict(extra="forbid")

    agent_spec_id: int
    workspace_id: int
    name: NonEmptyStr
    source: NonEmptyStr
    event_type: NonEmptyStr
    condition: dict[str, Any]
    concurrency_key: str | None = None

    @property
    def normalized_concurrency_key(self) -> str | None:
        if self.concurrency_key is None:
            return None
        normalized = self.concurrency_key.strip()
        return normalized or None


@dataclass(slots=True, frozen=True)
class AgentTriggerSubscriptionDefinition:
    """저장된 policy에서 파생한 webhook routing row 정의."""

    source: str
    event_type: str
    role: str


@dataclass(slots=True, frozen=True)
class AgentTriggerEventCandidate:
    """subscription routing row로 식별한 trigger와 해당 event의 role hint."""

    trigger: AgentTrigger
    roles: frozenset[str]


def derive_trigger_event_subscriptions(
    *,
    source: str,
    primary_event_type: str,
    policy: ImmediatePolicy | DebouncePolicy,
) -> tuple[AgentTriggerSubscriptionDefinition, ...]:
    if isinstance(policy, ImmediatePolicy):
        return (
            AgentTriggerSubscriptionDefinition(
                source=source,
                event_type=primary_event_type,
                role=TRIGGER_EVENT_ROLE_PRIMARY,
            ),
        )

    definitions = [
        AgentTriggerSubscriptionDefinition(
            source=source,
            event_type=policy.start_event_type,
            role=TRIGGER_EVENT_ROLE_START,
        )
    ]
    seen_reset_events: set[str] = set()
    for event_type in policy.reset_event_types:
        if event_type in seen_reset_events:
            continue
        seen_reset_events.add(event_type)
        definitions.append(
            AgentTriggerSubscriptionDefinition(
                source=source,
                event_type=event_type,
                role=TRIGGER_EVENT_ROLE_RESET,
            )
        )
    return tuple(definitions)


def create_or_update_agent_trigger_from_definition(
    db: Session,
    definition: AgentTriggerDefinition,
) -> AgentTrigger:
    agent_spec = db.scalar(
        select(AgentSpec).where(AgentSpec.id == definition.agent_spec_id)
    )
    if agent_spec is None:
        raise AgentTriggerDefinitionError(
            f"AgentSpec not found: {definition.agent_spec_id}"
        )
    if agent_spec.workspace_id != definition.workspace_id:
        raise AgentTriggerDefinitionError(
            "AgentTrigger workspace_id must match AgentSpec.workspace_id"
        )

    policy = parse_policy(definition.condition)
    _require_provider_trigger_boundary(source=definition.source, policy=policy)
    canonical_condition = policy.model_dump(mode="json")
    concurrency_key = definition.normalized_concurrency_key
    subscription_definitions = derive_trigger_event_subscriptions(
        source=definition.source,
        primary_event_type=definition.event_type,
        policy=policy,
    )

    trigger = db.scalar(
        select(AgentTrigger).where(
            AgentTrigger.agent_spec_id == definition.agent_spec_id,
            AgentTrigger.source == definition.source,
            AgentTrigger.event_type == definition.event_type,
        )
    )

    if trigger is None:
        trigger = AgentTrigger(
            agent_spec_id=definition.agent_spec_id,
            type="webhook",
            source=definition.source,
            event_type=definition.event_type,
        )
        db.add(trigger)

    trigger.workspace_id = definition.workspace_id
    trigger.name = definition.name
    trigger.condition = canonical_condition
    trigger.concurrency_key = concurrency_key

    db.flush()
    _refresh_trigger_event_subscriptions(
        db=db,
        trigger=trigger,
        subscriptions=subscription_definitions,
    )
    db.flush()
    return trigger


def _require_provider_trigger_boundary(
    *,
    source: str,
    policy: ImmediatePolicy | DebouncePolicy,
) -> None:
    if source != "channel_talk":
        return
    if isinstance(policy, ImmediatePolicy):
        _require_channel_talk_channel_clause(policy.where, field_name="where")
        return

    _require_channel_talk_channel_clause(policy.where, field_name="where")
    _require_channel_talk_channel_clause(policy.reset_where, field_name="reset_where")


def _require_channel_talk_channel_clause(where: Any, *, field_name: str) -> None:
    if _has_channel_talk_channel_clause(where):
        return
    raise AgentTriggerDefinitionError(
        "Channel Talk trigger condition must include "
        f"$.payload.entity.channelId eq/in clause in {field_name}"
    )


def _has_channel_talk_channel_clause(where: Any) -> bool:
    if not isinstance(where, dict):
        return False
    for group_key in ("all", "any"):
        clauses = where.get(group_key)
        if isinstance(clauses, list) and any(
            _has_channel_talk_channel_clause(clause) for clause in clauses
        ):
            return True
    if where.get("path") != "$.payload.entity.channelId":
        return False
    operator = where.get("op")
    value = where.get("value")
    if operator == "eq":
        return isinstance(value, str) and bool(value.strip())
    if operator == "in":
        return isinstance(value, list) and any(
            isinstance(item, str) and bool(item.strip()) for item in value
        )
    return False


def get_trigger_event_subscription_candidates(
    db: Session,
    *,
    source: str,
    event_type: str,
) -> list[AgentTriggerEventCandidate]:
    subscription_stmt = (
        select(
            AgentTriggerEventSubscription.trigger_id,
            AgentTriggerEventSubscription.role,
        )
        .where(
            AgentTriggerEventSubscription.source == source,
            AgentTriggerEventSubscription.event_type == event_type,
        )
        .order_by(AgentTriggerEventSubscription.trigger_id.asc())
    )
    roles_by_trigger_id: dict[int, set[str]] = {}
    ordered_trigger_ids: list[int] = []

    # trigger_id 단위 중복 제거 및 role 집계
    for trigger_id, role in db.execute(subscription_stmt).all():
        if trigger_id not in roles_by_trigger_id:
            ordered_trigger_ids.append(trigger_id)
        roles_by_trigger_id.setdefault(trigger_id, set()).add(role)

    if not ordered_trigger_ids:
        return []

    trigger_stmt = (
        select(AgentTrigger)
        .options(selectinload(AgentTrigger.agent_spec))
        .where(AgentTrigger.id.in_(ordered_trigger_ids))
    )
    triggers_by_id = {trigger.id: trigger for trigger in db.scalars(trigger_stmt).all()}

    return [
        AgentTriggerEventCandidate(
            trigger=trigger,
            roles=frozenset(roles_by_trigger_id[trigger_id]),
        )
        for trigger_id in ordered_trigger_ids
        if (trigger := triggers_by_id.get(trigger_id)) is not None
    ]


def _refresh_trigger_event_subscriptions(
    *,
    db: Session,
    trigger: AgentTrigger,
    subscriptions: tuple[AgentTriggerSubscriptionDefinition, ...],
) -> None:
    db.execute(
        delete(AgentTriggerEventSubscription).where(
            AgentTriggerEventSubscription.trigger_id == trigger.id
        )
    )
    for subscription in subscriptions:
        db.add(
            AgentTriggerEventSubscription(
                trigger=trigger,
                source=subscription.source,
                event_type=subscription.event_type,
                role=subscription.role,
            )
        )
