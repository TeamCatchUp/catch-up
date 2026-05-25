from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import AgentTrigger


def get_webhook_triggers(db: Session, source: str) -> list[AgentTrigger]:
    """source가 일치하는 webhook 타입 AgentTrigger 목록을 조회한다."""
    stmt = select(AgentTrigger).where(
        AgentTrigger.type == "webhook",
        AgentTrigger.source == source,
    )
    return list(db.scalars(stmt).all())
