from typing import Annotated
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.agents.triggers.validator import trigger_policy_validator
from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTrigger

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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

    policy = trigger_policy_validator.validate_policy(definition.condition)
    canonical_condition = policy.model_dump(mode="json")
    concurrency_key = definition.normalized_concurrency_key

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
    return trigger


def get_active_webhook_triggers(
    db: Session,
    *,
    workspace_id: int,
    source: str,
    event_type: str,
) -> list[AgentTrigger]:
    """정규화된 webhook event에 해당하고 활성 AgentSpec에 연결된 트리거를 조회한다."""
    stmt = (
        select(AgentTrigger)
        .join(AgentTrigger.agent_spec)
        .where(
            AgentTrigger.type == "webhook",
            AgentTrigger.workspace_id == workspace_id,
            AgentTrigger.source == source,
            AgentTrigger.event_type == event_type,
            AgentSpec.status == AgentStatus.ACTIVE,
        )
    )
    return list(db.scalars(stmt).all())
