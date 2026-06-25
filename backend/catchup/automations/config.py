from __future__ import annotations

from pydantic import BaseModel

INQUIRY_AUTOMATION_PRESET_KEY = "channel_talk_slack_response_guide"


class InquiryAutomationConfig(BaseModel):
    preset_key: str
    channel_talk_credential_id: int
    slack_channel_id: str
    slack_credential_id: int
    guide_instruction: str | None = None
    quiet_period_seconds: int | None = None
