import structlog
from sqlalchemy.orm import Session

from catchup.agents.factory import get_execution_service
from catchup.agents.schemas import AgentSpec
from catchup.agents.tools.internal.search import CatchUpKnowledgeBaseTool
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.policies import ImmediatePolicy
from catchup.agents.triggers.policies import PolicyValidationError
from catchup.agents.triggers.validator import trigger_policy_validator
from catchup.db.agent_specs import build_agent_global_context
from catchup.db.agent_triggers import get_active_webhook_triggers
from catchup.db.models import AgentTrigger

logger = structlog.get_logger(__name__)


def _trigger_matches_event(trigger: AgentTrigger, event: AgentWebhookEvent) -> bool:
    try:
        policy = trigger_policy_validator.validate_policy(trigger.condition)
    except PolicyValidationError as exc:
        logger.warning(
            "invalid_trigger_policy_ignored",
            trigger_id=trigger.id,
            event_id=event.event_id,
            reason=str(exc),
        )
        return False

    return isinstance(policy, ImmediatePolicy)


def _resolve_triggers(
    db: Session,
    event: AgentWebhookEvent,
) -> list[AgentTrigger]:
    """Webhook event에 매칭되는 AgentTrigger 목록을 반환한다.

    workspace/source/event_type이 일치하는 활성 트리거를 조회한 뒤
    Phase 1에서는 immediate policy만 dispatch 대상으로 둔다.
    """
    triggers = get_active_webhook_triggers(
        db,
        workspace_id=event.workspace_id,
        source=event.source,
        event_type=event.event_type,
    )

    return [
        trigger
        for trigger in triggers
        if _trigger_matches_event(trigger, event)
    ]


def _matches_event_workspace(agent_spec_row, event: AgentWebhookEvent) -> bool:
    return agent_spec_row.workspace_id == event.workspace_id


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
            if _matches_event_workspace(candidate.agent_spec, event)
        ),
        None,
    )

    if trigger is None:
        log.info(
            "no_workspace_matching_agent_spec_for_matched_triggers",
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
