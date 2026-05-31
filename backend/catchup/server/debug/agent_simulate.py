"""Execution Agent 디버그용 엔드포인트.

실제 웹훅 엔드포인트는 각 커넥터 담당자가 구현한다.
이 라우터는 Swagger에서 웹훅 수신을 시뮬레이션하기 위한 용도로만 사용한다.
"""
import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy.orm import Session

from catchup.agents.triggers.channel_talk_context import (
    CHANNEL_TALK_USER_CHAT_CONTEXT_KEY,
)
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.resolver import handle_agent_webhook_event
from catchup.db.agent_triggers import AgentTriggerDefinition
from catchup.db.agent_triggers import AgentTriggerDefinitionError
from catchup.db.agent_triggers import create_or_update_agent_trigger_from_definition
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.dependencies import get_db
from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


class WebhookSimulateResponse(AgentWebhookEvent):
    status: str
    reason: str | None = None
    run_ids: list[int] = Field(default_factory=list)
    matched_count: int = 0
    result: str | None
    matched: bool


class ChannelTalkCredentialOption(BaseModel):
    channel_id: str
    channel_name: str
    credential_last_verified_at: str | None = None
    webhook_token_configured: bool


class ChannelTalkDebounceTriggerRequest(BaseModel):
    agent_spec_id: int
    channel_id: str = Field(min_length=1)
    name: str | None = None
    quiet_period_seconds: int = Field(default=60, ge=1)


class ChannelTalkDebounceTriggerResponse(BaseModel):
    trigger_id: int
    agent_spec_id: int
    channel_id: str
    name: str
    quiet_period_seconds: int
    context_input_key: str
    start_event_type: str
    reset_event_types: list[str]


@router.post(
    "/simulate-webhook",
    response_model=WebhookSimulateResponse,
    status_code=status.HTTP_200_OK,
    summary="웹훅 수신 시뮬레이션 (디버그용)",
    description=(
        "정규화된 AgentWebhookEvent를 지정해 trigger resolver → run/outbox 저장 흐름을 테스트한다. "
        "agent_triggers에 매칭되는 트리거가 없으면 matched=false를 반환한다."
    ),
)
async def simulate_webhook(
    body: AgentWebhookEvent,
    db: Session = Depends(get_db),
) -> WebhookSimulateResponse:
    try:
        ingress = handle_agent_webhook_event(
            db=db,
            event=body,
        )
    except Exception as e:
        logger.exception(
            "simulate_webhook_error",
            event_id=body.event_id,
            source=body.source,
            event_type=body.event_type,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    run_ids = ingress.run_ids or []
    return WebhookSimulateResponse(
        **body.model_dump(),
        status=ingress.status,
        reason=ingress.reason,
        run_ids=run_ids,
        matched_count=ingress.matched_count,
        result=",".join(str(run_id) for run_id in run_ids) if run_ids else None,
        matched=ingress.status == "accepted",
    )


@router.get(
    "/channel-talk/credentials",
    response_model=list[ChannelTalkCredentialOption],
    status_code=status.HTTP_200_OK,
    summary="Channel Talk Credential 선택 목록 (디버그용)",
)
async def list_channel_talk_credentials(
    db: Session = Depends(get_db),
) -> list[ChannelTalkCredentialOption]:
    repository = ChannelTalkCredentialsRepository(db)
    return [
        ChannelTalkCredentialOption(
            channel_id=record.channel_id,
            channel_name=record.channel_name,
            credential_last_verified_at=(
                record.credential_last_verified_at.isoformat()
                if record.credential_last_verified_at is not None
                else None
            ),
            webhook_token_configured=record.webhook_token_configured,
        )
        for record in repository.list_connections()
    ]


@router.post(
    "/channel-talk/debounce-trigger",
    response_model=ChannelTalkDebounceTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Channel Talk UserChat debounce Trigger 등록 (디버그용)",
)
async def register_channel_talk_debounce_trigger(
    body: ChannelTalkDebounceTriggerRequest,
    db: Session = Depends(get_db),
) -> ChannelTalkDebounceTriggerResponse:
    channel_id = body.channel_id.strip()
    credential = ChannelTalkCredentialsRepository(db).get_connection(channel_id=channel_id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel Talk credentials not found",
        )

    agent_spec = db.get(AgentSpec, body.agent_spec_id)
    if agent_spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AgentSpec not found",
        )
    if agent_spec.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AgentSpec must be active to test trigger execution",
        )

    trigger_name = body.name or (
        f"Debug Channel Talk debounce - {credential.channel_name}"
    )
    condition = _channel_talk_debounce_condition(
        channel_id=channel_id,
        quiet_period_seconds=body.quiet_period_seconds,
    )
    try:
        trigger = create_or_update_agent_trigger_from_definition(
            db,
            AgentTriggerDefinition(
                agent_spec_id=agent_spec.id,
                workspace_id=agent_spec.workspace_id,
                name=trigger_name,
                source="channel_talk",
                event_type="user_chat.created",
                condition=condition,
                concurrency_key=f"channel_talk:{channel_id}:user_chat",
            ),
        )
        db.commit()
    except AgentTriggerDefinitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        logger.exception(
            "debug_channel_talk_debounce_trigger_registration_failed",
            agent_spec_id=body.agent_spec_id,
            channel_id=channel_id,
        )
        raise

    return ChannelTalkDebounceTriggerResponse(
        trigger_id=trigger.id,
        agent_spec_id=trigger.agent_spec_id,
        channel_id=channel_id,
        name=trigger.name,
        quiet_period_seconds=body.quiet_period_seconds,
        context_input_key=CHANNEL_TALK_USER_CHAT_CONTEXT_KEY,
        start_event_type="user_chat.created",
        reset_event_types=["user_chat.new_message"],
    )


def _channel_talk_debounce_condition(
    *,
    channel_id: str,
    quiet_period_seconds: int,
) -> dict:
    """공식 Channel Talk payload 경로만 사용하는 디버그용 debounce policy."""
    channel_boundary = {
        "path": "$.payload.entity.channelId",
        "op": "eq",
        "value": channel_id,
    }
    return {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": quiet_period_seconds,
        "run_context": "latest_event",
        "where": {"all": [channel_boundary]},
        "reset_where": {"all": [channel_boundary]},
    }
