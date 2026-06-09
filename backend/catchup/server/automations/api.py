from __future__ import annotations

import asyncio
import uuid
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
from catchup.automations.config import InquiryAutomationConfig
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.db.agent_triggers import AgentTriggerDefinition
from catchup.db.agent_triggers import AgentTriggerDefinitionError
from catchup.db.agent_triggers import create_or_update_agent_trigger_from_definition
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.dependencies import get_db
from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus
from catchup.db.models import SlackChannel
from catchup.db.models import User
from catchup.db.models import UserWorkspace
from catchup.db.slack.oauth_repository import get_slack_token_by_id

router = APIRouter(
    prefix="/api/v1/automations/inqueries",
    tags=["automations"],
)

_AGENT_ID_NAMESPACE = uuid.UUID("8d94ed94-b9c1-47b6-8716-e7a69e778a95")


class SlackChannelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: int = Field(gt=0)
    channel_id: str = Field(min_length=1)
    channel_name: str | None = Field(default=None, min_length=1)


class InquiryAutomationPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_talk_credential_id: int = Field(gt=0)
    quiet_period_seconds: int = Field(ge=1, le=86_400)
    slack_channel: SlackChannelSelection
    guide_instruction: str | None = None


class InquiryAutomationItem(BaseModel):
    agent_spec_id: int
    status: AgentStatus
    channel_talk_credential_id: int
    slack_channel_id: str
    slack_credential_id: int
    guide_instruction: str | None
    quiet_period_seconds: int | None
    trigger_id: int | None


class InquiryAutomationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AgentStatus


class InquiryAutomationPublishResponse(BaseModel):
    agent_spec_id: int
    trigger_id: int
    status: AgentStatus
    channel_talk_channel_id: str
    channel_talk_channel_name: str
    quiet_period_seconds: int
    slack_channel_id: str
    start_event_type: str
    reset_event_types: list[str]


@router.get(
    "",
    response_model=list[InquiryAutomationItem],
    status_code=status.HTTP_200_OK,
    summary="채널톡 문의 자동화 목록 조회",
)
def list_inquiry_automations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InquiryAutomationItem]:
    """워크스페이스에 등록된 문의 자동화 설정 목록을 반환한다."""
    workspace_id = _resolve_user_workspace_id(db, current_user.id)
    rows = db.scalars(
        select(AgentSpec).where(
            AgentSpec.workspace_id == workspace_id,
            AgentSpec.spec["preset_key"].as_string()
            == INQUIRY_AUTOMATION_PRESET_KEY,
        )
    ).all()

    items = []
    for row in rows:
        try:
            config = InquiryAutomationConfig.model_validate(row.spec)
        except Exception:
            continue
        trigger = row.triggers[0] if row.triggers else None
        quiet_period_seconds = None
        if trigger is not None:
            quiet_period_seconds = trigger.condition.get("quiet_period_seconds")
        items.append(
            InquiryAutomationItem(
                agent_spec_id=row.id,
                status=row.status,
                channel_talk_credential_id=config.channel_talk_credential_id,
                slack_channel_id=config.slack_channel_id,
                slack_credential_id=config.slack_credential_id,
                guide_instruction=config.guide_instruction,
                quiet_period_seconds=quiet_period_seconds,
                trigger_id=trigger.id if trigger is not None else None,
            )
        )
    return items


@router.patch(
    "/{agent_spec_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="채널톡 문의 자동화 상태 변경",
)
def update_inquiry_automation(
    agent_spec_id: int,
    body: InquiryAutomationUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """문의 자동화 상태를 변경한다. inactive로 비활성화, active로 재활성화한다."""
    workspace_id = _resolve_user_workspace_id(db, current_user.id)
    agent_spec = db.scalar(
        select(AgentSpec)
        .where(
            AgentSpec.id == agent_spec_id,
            AgentSpec.workspace_id == workspace_id,
            AgentSpec.spec["preset_key"].as_string()
            == INQUIRY_AUTOMATION_PRESET_KEY,
        )
        .with_for_update()
    )
    if agent_spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )
    agent_spec.status = body.status
    db.commit()


@router.post(
    "/publish",
    response_model=InquiryAutomationPublishResponse,
    status_code=status.HTTP_200_OK,
    summary="채널톡 문의 자동화 설정 생성 및 활성화",
)
def publish_inquiry_automation(
    body: InquiryAutomationPublishRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InquiryAutomationPublishResponse:
    """채널톡-슬랙 문의 자동화 설정을 신규 생성하고 즉시 활성화한다."""
    workspace_id = _resolve_user_workspace_id(db, current_user.id)

    channel_talk_credential = ChannelTalkCredentialsRepository(
        db
    ).get_connection_by_id(body.channel_talk_credential_id)
    if channel_talk_credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel Talk credentials not found",
        )
    if not channel_talk_credential.webhook_token_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel Talk webhook token is not configured",
        )

    slack_reference = _resolve_slack_channel_reference(db, body.slack_channel)

    agent_id = _build_agent_id(
        workspace_id=workspace_id,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id=channel_talk_credential.channel_id,
        slack_channel_id=str(slack_reference["channel_id"]),
    )
    config = InquiryAutomationConfig(
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_credential_id=body.channel_talk_credential_id,
        slack_channel_id=str(slack_reference["channel_id"]),
        slack_credential_id=slack_reference["credential_id"],
        guide_instruction=body.guide_instruction,
    )
    agent_spec = db.scalar(
        select(AgentSpec)
        .where(AgentSpec.agent_id == agent_id)
        .with_for_update()
    )
    if agent_spec is not None:
        agent_spec.spec = config.model_dump(mode="json")
        agent_spec.status = AgentStatus.ACTIVE
    else:
        agent_spec = AgentSpec(
            agent_id=agent_id,
            workspace_id=workspace_id,
            user_id=current_user.id,
            spec=config.model_dump(mode="json"),
            status=AgentStatus.ACTIVE,
        )
        db.add(agent_spec)
    db.flush()

    condition = _build_channel_talk_debounce_condition(
        channel_id=channel_talk_credential.channel_id,
        quiet_period_seconds=body.quiet_period_seconds,
    )
    try:
        trigger = create_or_update_agent_trigger_from_definition(
            db,
            AgentTriggerDefinition(
                agent_spec_id=agent_spec.id,
                workspace_id=agent_spec.workspace_id,
                name=(
                    f"Channel Talk debounce - {channel_talk_credential.channel_name}"
                ),
                source="channel_talk",
                event_type="user_chat.created",
                condition=condition,
                concurrency_key=(
                    f"channel_talk:{channel_talk_credential.channel_id}:user_chat"
                ),
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
        raise

    return InquiryAutomationPublishResponse(
        agent_spec_id=agent_spec.id,
        trigger_id=trigger.id,
        status=agent_spec.status,
        channel_talk_channel_id=channel_talk_credential.channel_id,
        channel_talk_channel_name=channel_talk_credential.channel_name,
        quiet_period_seconds=body.quiet_period_seconds,
        slack_channel_id=str(slack_reference["channel_id"]),
        start_event_type="user_chat.created",
        reset_event_types=["user_chat.new_message"],
    )


def _resolve_user_workspace_id(db: Session, user_id: int) -> int:
    workspace_link = db.scalar(
        select(UserWorkspace)
        .where(UserWorkspace.user_id == user_id)
        .order_by(UserWorkspace.joined_at.asc())
        .limit(1)
    )
    if workspace_link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not assigned to a workspace",
        )
    return workspace_link.workspace_id


def _build_agent_id(
    *,
    workspace_id: int,
    preset_key: str,
    channel_talk_channel_id: str,
    slack_channel_id: str,
) -> uuid.UUID:
    return uuid.uuid5(
        _AGENT_ID_NAMESPACE,
        ":".join(
            [
                str(workspace_id),
                preset_key,
                channel_talk_channel_id,
                slack_channel_id,
            ]
        ),
    )


def _resolve_slack_channel_reference(
    db: Session,
    selection: SlackChannelSelection,
) -> dict[str, Any]:
    slack_token = get_slack_token_by_id(db, selection.credential_id)
    if slack_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack credentials not found",
        )
    if not slack_token.bot_access_token or not slack_token.team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack credentials are incomplete",
        )

    channel = db.get(SlackChannel, selection.channel_id)
    channel_name = selection.channel_name
    if channel is not None:
        if channel.team_id != slack_token.team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slack channel does not belong to the selected credentials",
            )
        if channel.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slack channel is archived",
            )
        channel_name = channel.name
    if not channel_name:
        channel_name = selection.channel_id

    _validate_slack_channel_history_access(
        bot_access_token=slack_token.bot_access_token,
        team_id=slack_token.team_id,
        channel_id=selection.channel_id,
    )

    return {
        "channel_name": channel_name,
        "channel_id": selection.channel_id,
        "credential_id": selection.credential_id,
    }


def _validate_slack_channel_history_access(
    *,
    bot_access_token: str,
    team_id: str,
    channel_id: str,
) -> None:
    """Publish 전에 선택된 채널의 history read을 통해 Bot의 채널 초대 여부를 검증한다. """

    async def _probe() -> None:
        client = SlackApiClientWrapper(bot_access_token, team_id)
        await client.get_conversation_history(
            channel=channel_id,
            limit=1,
        )

    try:
        asyncio.run(_probe())
    except SlackConnectorApiError as exc:
        error_code = exc.metadata.get("error") if exc.metadata else None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Bot does not have access to the requested Slack Channel."
                + (f": {error_code}" if error_code else "")
            ),
        ) from exc



def _build_channel_talk_debounce_condition(
    *,
    channel_id: str,
    quiet_period_seconds: int,
) -> dict[str, Any]:
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
        "reset_where": {
            "all": [
                channel_boundary,
                {
                    "path": "$.payload.entity.personType",
                    "op": "eq",
                    "value": "user",
                },
            ]
        },
    }
