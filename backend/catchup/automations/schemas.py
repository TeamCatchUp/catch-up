from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import AgentStatus


class SlackChannelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: int = Field(gt=0)
    channel_id: str = Field(min_length=1)
    channel_name: str | None = Field(default=None, min_length=1)


class InquiryAutomationPatch(BaseModel):
    """문의 자동화 부분 수정 요청. 포함된 필드만 반영된다."""

    model_config = ConfigDict(extra="forbid")

    channel_talk_credential_id: int | None = Field(default=None, gt=0)
    quiet_period_seconds: int | None = Field(default=None, ge=1, le=86_400)
    slack_channel: SlackChannelSelection | None = None
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
    title: str
    author_name: str
    updated_at: str
    author_profile_image_url: str | None
    is_editable: bool


@dataclass
class InquiryAutomationPublishResult:
    agent_spec_id: int
    trigger_id: int
    status: AgentStatus
    channel_talk_channel_id: str
    channel_talk_channel_name: str
    quiet_period_seconds: int
    slack_channel_id: str
