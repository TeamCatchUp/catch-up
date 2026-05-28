import structlog
from sqlalchemy.orm import Session

from catchup.agents.factory import get_execution_service
from catchup.agents.schemas import AgentSpec
from catchup.agents.tools.internal.search import CatchUpKnowledgeBaseTool
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.db.agent_specs import build_agent_global_context
from catchup.db.agent_triggers import get_webhook_triggers
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTrigger

logger = structlog.get_logger(__name__)


# TODO : conditon operation 추가
def _matches_filter_condition(
    payload: dict,
    filter_condition: dict | None,
) -> bool:
    condition = filter_condition or {}
    return all(payload.get(k) == v for k, v in condition.items())


def _resolve_triggers(
    db: Session,
    event: AgentWebhookEvent,
) -> list[AgentTrigger]:
    """Webhook event에 매칭되는 AgentTrigger 목록을 반환한다.

    source가 일치하는 트리거를 조회한 뒤 기존 filter_condition의 모든 KV가 event.payload에 존재하는지 검증함
    """
    triggers = get_webhook_triggers(db, event.source)

    return [
        trigger
        for trigger in triggers
        if _matches_filter_condition(event.payload, trigger.filter_condition)
    ]


def _is_runnable_agent_spec(agent_spec_row, event: AgentWebhookEvent) -> bool:
    return (
        agent_spec_row.status == AgentStatus.ACTIVE
        and agent_spec_row.workspace_id == event.workspace_id
    )


async def dispatch_webhook_event(
    db: Session,
    event: AgentWebhookEvent,
) -> str | None:
    """정규화된 webhook event를 받아 매칭된 Execution Agent를 실행한다.

    매칭되는 트리거가 없으면 None을 반환한다.
    """
    log = logger.bind(
        event_id=event.event_id,
        source=event.source,
        event_type=event.event_type,
        workspace_id=event.workspace_id,
    )
    
    triggers = _resolve_triggers(db, event)

    if not triggers:
        log.warning("no_matching_trigger")
        return None

    trigger = next(
        (
            candidate
            for candidate in triggers
            if _is_runnable_agent_spec(candidate.agent_spec, event)
        ),
        None,
    )

    if trigger is None:
        log.info(
            "no_active_agent_spec_for_matched_triggers",
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

    log.bind(
        trigger_id=trigger.id,
        agent_spec_id=agent_spec_row.id,
        agent_name=spec.name,
    ).info(
        "trigger_matched",
        matched_count=len(triggers),
    )

    service = get_execution_service()
    return await service.run(
        spec_id=agent_spec_row.id,
        spec=spec,
        user_input_values=user_input_values,
        trigger_event=event,
    )
