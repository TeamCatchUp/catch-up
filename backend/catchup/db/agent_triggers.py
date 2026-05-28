from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTrigger


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
