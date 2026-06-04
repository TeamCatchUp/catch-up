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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from catchup.agents.schemas import AgentSpec as AgentSpecSchema
from catchup.auth.dependencies import get_current_user
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
    prefix="/api/v1/agent/build",
    tags=["agent-build"],
)

PRESET_KEY = "channel_talk_slack_response_guide"
SLACK_FIND_TOOL_NAME = "slack.find_channel_talk_user_chat_message"
SLACK_SEND_TOOL_NAME = "slack.send_thread_message"
AGENT_ID_NAMESPACE = uuid.UUID("8d94ed94-b9c1-47b6-8716-e7a69e778a95")


class SlackChannelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: int = Field(gt=0)
    channel_id: str = Field(min_length=1)
    channel_name: str | None = Field(default=None, min_length=1)


class TempAgentPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_key: str = PRESET_KEY
    channel_talk_credential_id: int = Field(gt=0)
    quiet_period_seconds: int = Field(ge=1, le=86_400)
    slack_channel: SlackChannelSelection


class TempAgentPublishResponse(BaseModel):
    agent_spec_id: int
    preset_key: str
    trigger_id: int
    status: AgentStatus
    channel_talk_channel_id: str
    channel_talk_channel_name: str
    quiet_period_seconds: int
    slack_channel_id: str
    configured_reference_tools: list[str]
    start_event_type: str
    reset_event_types: list[str]


@router.post(
    "/temp/publish",
    response_model=TempAgentPublishResponse,
    status_code=status.HTTP_200_OK,
    summary="문의 자동화 v0 빌드 및 Publish MVP 엔드포인트",
)
def publish_temp_agent(
    body: TempAgentPublishRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TempAgentPublishResponse:
    """Preset 기반 AgentSpec/Trigger를 신규 생성하고 즉시 활성화한다."""

    if body.preset_key != PRESET_KEY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported preset_key",
        )

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


    agent_id = _build_preset_agent_id(
        workspace_id=workspace_id,
        preset_key=body.preset_key,
        channel_talk_channel_id=channel_talk_credential.channel_id,
        slack_channel_id=str(slack_reference["channel_id"]),
    )
    existing_agent_spec = db.scalar(
        select(AgentSpec)
        .where(AgentSpec.agent_id == agent_id)
        .with_for_update()
    )
    if existing_agent_spec is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AgentSpec already exists for this preset and channel selection",
        )

    #  Preset spec에 고객사 Slack reference 값을 주입해 완성된 AgentSpec을 만든다.
    references = _build_references(
        slack_reference=slack_reference,
    )
    spec = _build_preset_agent_spec(references=references)
    agent_spec = AgentSpec(
        agent_id=agent_id,
        workspace_id=workspace_id,
        user_id=current_user.id,
        spec=spec.model_dump(mode="json"),
        status=AgentStatus.ACTIVE,
    )
    db.add(agent_spec)
    db.flush()

    # Trigger condition & Trigger Subscription 생성
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
                name=f"Channel Talk debounce - {channel_talk_credential.channel_name}",
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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AgentSpec already exists for this preset and channel selection",
        ) from exc
    except Exception:
        db.rollback()
        raise

    return TempAgentPublishResponse(
        agent_spec_id=agent_spec.id,
        preset_key=body.preset_key,
        trigger_id=trigger.id,
        status=agent_spec.status,
        channel_talk_channel_id=channel_talk_credential.channel_id,
        channel_talk_channel_name=channel_talk_credential.channel_name,
        quiet_period_seconds=body.quiet_period_seconds,
        slack_channel_id=str(slack_reference["channel_id"]),
        configured_reference_tools=sorted(references.keys()),
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


def _build_preset_agent_id(
    *,
    workspace_id: int,
    preset_key: str,
    channel_talk_channel_id: str,
    slack_channel_id: str,
) -> uuid.UUID:
    return uuid.uuid5(
        AGENT_ID_NAMESPACE,
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


def _build_references(
    *,
    slack_reference: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    slack_reference_key = str(slack_reference["channel_name"])
    slack_value = {
        "channel_id": slack_reference["channel_id"],
        "credential_id": slack_reference["credential_id"],
    }
    references: dict[str, list[dict[str, Any]]] = {}
    for tool_name in (SLACK_FIND_TOOL_NAME, SLACK_SEND_TOOL_NAME):
        references[tool_name] = [
            {
                "argument": "channel_name",
                "kind": "slack_channel",
                "values": {
                    slack_reference_key: slack_value,
                },
            }
        ]
    return references


def _build_preset_agent_spec(
    *,
    references: dict[str, list[dict[str, Any]]],
) -> AgentSpecSchema:
    return AgentSpecSchema.model_validate(
        {
            "agent_id": PRESET_KEY,
            "name": "Channel Talk Slack Response Guide",
            "system_prompt": {
                "role": "채널톡으로 인입된 고객 문의를 분석하고, 지식베이스를 검색해 관련 맥락을 찾은 뒤 CS 담당자가 바로 활용할 수 있는 문의대응 가이드 초안을 작성하는 에이전트입니다.",
                "background": "B2B SaaS 고객사. 고객 문의는 결제/기술/일반 세 카테고리로 분류됩니다. CS 담당자는 초안을 바탕으로 고객에게 직접 답변합니다.",
                "execution_guidelines": (
                    "Step 1: [No tool] Read the customer inquiry from the user input field named 'channel_talk_user_chat_context'. This context contains the accumulated Channel Talk UserChat messages available at execution time. If the content is not a substantive inquiry (e.g., a greeting, thank-you, acknowledgement, or single-word response), skip Steps 2–3 and prepare a natural Korean guide draft. Otherwise, classify the inquiry into one of: 결제 / 기술 / 일반.\n"
                    "Step 2: [catchup_kb.search × 1–3] Search the knowledge base. Always set original_query to the exact value of the user input field 'channel_talk_user_chat_context'. Set query to an English semantic search phrase targeting a specific aspect of the inquiry. Repeat with a different query angle if the returned passages are insufficient or miss key aspects — each call accumulates results independently.\n"
                    "Step 3: [catchup_kb.rerank × 1] Once all searches are done, rerank the accumulated results. Set original_query to the exact value of the user input field 'channel_talk_user_chat_context'. Returns the final ranked passages — do not expect a generated answer.\n"
                    "Step 4: [No tool] Write a response guide draft in Korean for the CS agent. Structure: (1) 문의 요약 (one sentence), (2) 관련 맥락 (key facts from passages, or '확인된 관련 문서 없음' if search was skipped/insufficient), (3) 권장 답변 초안 (2-3 sentences the CS agent can send to the customer).\n"
                    "Step 5: [slack.find_channel_talk_user_chat_message × 1] Find the Slack message linked to this Channel Talk UserChat. Use channel_name='채널톡 연동 채널'. Set user_chat_id to the exact value of the user input field 'channel_talk_user_chat_id'.\n"
                    "Step 6: [slack.send_thread_message × 1] Send the Korean response guide draft from Step 4 to the Slack thread found in Step 5. Use channel_name='채널톡 연동 채널'. Set message_ts to the message_ts returned by Step 5. Set message to the full guide draft. If Slack lookup or delivery fails, do not retry manually; return the guide draft and mention that Slack delivery failed."
                ),
            },
            "tools": [
                {
                    "name": "catchup_kb.search",
                    "max_retry": 1,
                    "failure_policy": "skip",
                },
                {
                    "name": "catchup_kb.rerank",
                    "max_retry": 1,
                    "failure_policy": "skip",
                },
                {
                    "name": SLACK_FIND_TOOL_NAME,
                    "max_retry": 1,
                    "failure_policy": "continue",
                },
                {
                    "name": SLACK_SEND_TOOL_NAME,
                    "max_retry": 2,
                    "failure_policy": "continue",
                },
            ],
            "references": references,
            "execution_order": [
                "catchup_kb.search",
                "catchup_kb.rerank",
                SLACK_FIND_TOOL_NAME,
                SLACK_SEND_TOOL_NAME,
            ],
        }
    )


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
