import structlog
from sqlalchemy.orm import Session

from catchup.agents.factory import get_execution_service
from catchup.agents.schemas import AgentSpec
from catchup.agents.tools.internal.search import CatchUpKnowledgeBaseTool
from catchup.db.agent_specs import build_agent_global_context
from catchup.db.agent_triggers import get_webhook_triggers
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTrigger

logger = structlog.get_logger(__name__)


def _matches_filter_condition(
    payload: dict,
    filter_condition: dict | None,
) -> bool:
    condition = filter_condition or {}
    return all(payload.get(k) == v for k, v in condition.items())


def _resolve_triggers(
    db: Session,
    source: str,
    payload: dict,
) -> list[AgentTrigger]:
    """웹훅 payload에 매칭되는 AgentTrigger 목록을 반환한다.

    source가 일치하는 트리거를 조회한 뒤
    filter_condition의 모든 KV가 payload에 존재하는 트리거를 모두 반환한다.
    """
    triggers = get_webhook_triggers(db, source)

    return [
        trigger
        for trigger in triggers
        if _matches_filter_condition(payload, trigger.filter_condition)
    ]


def _is_active_agent_spec(agent_spec_row) -> bool:
    return agent_spec_row.status == AgentStatus.ACTIVE


async def dispatch_webhook(
    db: Session,
    source: str,
    payload: dict,
) -> str | None:
    """웹훅 payload를 받아 매칭된 Execution Agent를 실행하고 결과를 반환한다.

    매칭되는 트리거가 없으면 None을 반환한다.
    """
    triggers = _resolve_triggers(db, source, payload)

    if not triggers:
        logger.warning("no_matching_trigger", source=source)
        return None

    logger.info(
        "triggers_matched",
        source=source,
        matched_count=len(triggers),
    )

    trigger = next(
        (
            candidate
            for candidate in triggers
            if _is_active_agent_spec(candidate.agent_spec)
        ),
        None,
    )

    if trigger is None:
        logger.info(
            "no_active_agent_spec_for_matched_triggers",
            source=source,
            matched_count=len(triggers),
        )
        return None

    agent_spec_row = trigger.agent_spec
    spec = AgentSpec.model_validate(agent_spec_row.spec)
    user_input_values = agent_spec_row.user_input_values or {}

    global_context = build_agent_global_context(
        db=db,
        workspace_id=agent_spec_row.workspace_id,
        user_id=agent_spec_row.user_id,
    )
    CatchUpKnowledgeBaseTool.bind(global_context)

    logger.info(
        "trigger_matched",
        source=source,
        matched_count=len(triggers),
        trigger_id=trigger.id,
        agent_spec_id=agent_spec_row.id,
        agent_name=spec.name,
    )

    service = get_execution_service()
    return await service.run(
        spec_id=agent_spec_row.id,
        spec=spec,
        user_input_values=user_input_values,
        trigger_payload=payload,
    )
