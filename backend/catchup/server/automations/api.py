from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from typing import Any
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.automations.service import AutomationNotFoundError
from catchup.automations.service import AutomationPublishError
from catchup.automations.service import InquiryAutomationItem
from catchup.automations.service import InquiryAutomationService
from catchup.db.automations import get_workspace_id_for_user
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.dependencies import get_db
from catchup.db.models import AgentStatus
from catchup.db.models import User
from catchup.db.slack.oauth_repository import get_all_slack_tokens

router = APIRouter(
    prefix="/api/v1/automations",
    tags=["automations"],
)


class SlackChannelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: int = Field(gt=0)
    channel_id: str = Field(min_length=1)
    channel_name: str | None = Field(default=None, min_length=1)


class AutomationConnector(StrEnum):
    SLACK = "slack"
    CHANNEL_TALK = "channel_talk"


class AutomationCredentialItem(BaseModel):
    connector: str
    credential_id: int
    display_name: str
    external_id: str
    external_name: str | None = None
    is_configured: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutomationCredentialsResponse(BaseModel):
    connector: str
    total_credentials: int
    credentials: list[AutomationCredentialItem] = Field(default_factory=list)


class AutomationTargetItem(BaseModel):
    connector: str
    credential_id: int | None = None
    target_id: str
    display_name: str
    target_type: str
    is_accessible: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutomationTargetsResponse(BaseModel):
    connector: str
    credential_id: int | None = None
    total_targets: int
    targets: list[AutomationTargetItem] = Field(default_factory=list)


class InquiryAutomationPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_talk_credential_id: int = Field(gt=0)
    quiet_period_seconds: int = Field(ge=1, le=86_400)
    slack_channel: SlackChannelSelection
    guide_instruction: str | None = None


class InquiryAutomationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[AgentStatus.ACTIVE, AgentStatus.INACTIVE]


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
    "/credentials",
    response_model=AutomationCredentialsResponse,
    status_code=status.HTTP_200_OK,
    summary="문의 자동화 Credential 선택 목록 조회",
)
def list_automation_credentials(
    connector: Annotated[
        AutomationConnector,
        Query(description="automation connector: slack | channel_talk"),
    ],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AutomationCredentialsResponse:
    """문의 자동화 설정에 사용할 Credential 선택 목록을 반환한다."""
    _ = current_user
    if connector == AutomationConnector.SLACK:
        credentials = [
            AutomationCredentialItem(
                connector="slack",
                credential_id=int(t.id),
                display_name=_text(t.team_name) or str(t.team_id),
                external_id=str(t.team_id),
                external_name=_text(t.team_name),
                is_configured=bool(t.bot_access_token and t.team_id),
                metadata={
                    "team_id": str(t.team_id),
                    "team_name": _text(t.team_name),
                    "bot_user_id": _text(t.bot_user_id),
                    "bot_scopes": _text(t.bot_scopes),
                },
            )
            for t in get_all_slack_tokens(db)
        ]
    else:
        credentials = [
            AutomationCredentialItem(
                connector="channel_talk",
                credential_id=int(r.id),
                display_name=str(r.channel_name),
                external_id=str(r.channel_id),
                external_name=str(r.channel_name),
                is_configured=bool(r.webhook_token_configured),
                metadata={
                    "channel_id": str(r.channel_id),
                    "channel_name": str(r.channel_name),
                    "credential_last_verified_at": (
                        r.credential_last_verified_at.isoformat()
                        if r.credential_last_verified_at is not None
                        else None
                    ),
                    "webhook_token_configured": bool(r.webhook_token_configured),
                },
            )
            for r in ChannelTalkCredentialsRepository(db).list_connections()
            if r.id is not None
        ]

    return AutomationCredentialsResponse(
        connector=connector,
        total_credentials=len(credentials),
        credentials=credentials,
    )


@router.get(
    "/targets",
    response_model=AutomationTargetsResponse,
    status_code=status.HTTP_200_OK,
    summary="문의 자동화 Target 선택 목록 조회",
)
def list_automation_targets(
    connector: Annotated[
        AutomationConnector,
        Query(description="automation connector: slack | channel_talk"),
    ],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    credential_id: Annotated[
        int | None,
        Query(gt=0, description="optional credential row id"),
    ] = None,
) -> AutomationTargetsResponse:
    """문의 자동화 설정에 사용할 Slack Channel 등 target 선택 목록을 반환한다."""
    _ = current_user
    svc = InquiryAutomationService()
    try:
        if connector == AutomationConnector.SLACK:
            raw = svc.list_slack_targets(db, credential_id=credential_id)
        else:
            raw = svc.list_channel_talk_targets(db, credential_id=credential_id)
    except AutomationPublishError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    return AutomationTargetsResponse(
        connector=connector,
        credential_id=credential_id,
        total_targets=len(raw),
        targets=[AutomationTargetItem(**item) for item in raw],
    )


@router.get(
    "/inquiries",
    response_model=list[InquiryAutomationItem],
    status_code=status.HTTP_200_OK,
    summary="채널톡 문의 자동화 목록 조회",
)
def list_inquiry_automations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InquiryAutomationItem]:
    """워크스페이스에 등록된 문의 자동화 설정 목록을 반환한다."""
    workspace_id = _require_workspace_id(db, current_user.id)
    return InquiryAutomationService().list_automations(db, workspace_id)


@router.patch(
    "/inquiries/{agent_spec_id}",
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
    workspace_id = _require_workspace_id(db, current_user.id)
    try:
        InquiryAutomationService().update_status(
            db,
            agent_spec_id=agent_spec_id,
            workspace_id=workspace_id,
            new_status=body.status,
        )
    except AutomationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/inquiries/publish",
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
    workspace_id = _require_workspace_id(db, current_user.id)
    try:
        result = InquiryAutomationService().publish(
            db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            channel_talk_credential_id=body.channel_talk_credential_id,
            quiet_period_seconds=body.quiet_period_seconds,
            slack_credential_id=body.slack_channel.credential_id,
            slack_channel_id=body.slack_channel.channel_id,
            guide_instruction=body.guide_instruction,
        )
    except AutomationPublishError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=str(exc),
        ) from exc

    return InquiryAutomationPublishResponse(
        agent_spec_id=result.agent_spec_id,
        trigger_id=result.trigger_id,
        status=result.status,
        channel_talk_channel_id=result.channel_talk_channel_id,
        channel_talk_channel_name=result.channel_talk_channel_name,
        quiet_period_seconds=result.quiet_period_seconds,
        slack_channel_id=result.slack_channel_id,
        start_event_type="user_chat.created",
        reset_event_types=["user_chat.new_message"],
    )


def _require_workspace_id(db: Session, user_id: int) -> int:
    workspace_id = get_workspace_id_for_user(db, user_id)
    if workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not assigned to a workspace",
        )
    return workspace_id


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
