import pytest
from pydantic import ValidationError

from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
from catchup.automations.config import InquiryAutomationConfig


def test_inquiry_automation_config_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        InquiryAutomationConfig.model_validate(
            {
                "preset_key": INQUIRY_AUTOMATION_PRESET_KEY,
                "channel_talk_credential_id": 1,
            }
        )


def test_inquiry_automation_config_guide_instruction_optional() -> None:
    config = InquiryAutomationConfig(
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_credential_id=1,
        slack_channel_id="C123",
        slack_credential_id=42,
    )
    assert config.guide_instruction is None


def test_inquiry_automation_config_serializes_to_json() -> None:
    config = InquiryAutomationConfig(
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_credential_id=7,
        slack_channel_id="C456",
        slack_credential_id=99,
        guide_instruction="결제 문의 시 영수증 요청 필수",
    )
    data = config.model_dump(mode="json")
    assert data["slack_channel_id"] == "C456"
    assert data["guide_instruction"] == "결제 문의 시 영수증 요청 필수"
