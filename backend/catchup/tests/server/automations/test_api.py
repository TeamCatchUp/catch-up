import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.server.automations import api
from catchup.server.automations.api import InquiryAutomationPublishRequest
from catchup.server.automations.api import _build_agent_id
from catchup.server.automations.api import _build_channel_talk_debounce_condition
from catchup.server.automations.api import _validate_slack_channel_history_access


def test_publish_request_requires_slack_channel() -> None:
    with pytest.raises(ValidationError):
        InquiryAutomationPublishRequest.model_validate(
            {
                "channel_talk_credential_id": 7,
                "quiet_period_seconds": 60,
            }
        )


def test_publish_request_guide_instruction_is_optional() -> None:
    req = InquiryAutomationPublishRequest.model_validate(
        {
            "channel_talk_credential_id": 7,
            "quiet_period_seconds": 60,
            "slack_channel": {
                "credential_id": 1,
                "channel_id": "C123",
            },
        }
    )
    assert req.guide_instruction is None


def test_publish_request_accepts_guide_instruction() -> None:
    req = InquiryAutomationPublishRequest.model_validate(
        {
            "channel_talk_credential_id": 7,
            "quiet_period_seconds": 60,
            "slack_channel": {
                "credential_id": 1,
                "channel_id": "C123",
            },
            "guide_instruction": "결제 문의는 영수증을 요청하세요.",
        }
    )
    assert req.guide_instruction == "결제 문의는 영수증을 요청하세요."


def test_build_agent_id_is_stable_for_idempotency_key() -> None:
    first = _build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    second = _build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    assert first == second


def test_build_agent_id_differs_for_different_slack_channels() -> None:
    a = _build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    b = _build_agent_id(
        workspace_id=1,
        preset_key=INQUIRY_AUTOMATION_PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C999",
    )
    assert a != b


def test_build_channel_talk_debounce_condition_resets_only_user_messages() -> None:
    condition = _build_channel_talk_debounce_condition(
        channel_id="229395",
        quiet_period_seconds=60,
    )
    assert condition == {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": 60,
        "run_context": "latest_event",
        "where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "229395",
                }
            ]
        },
        "reset_where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "229395",
                },
                {
                    "path": "$.payload.entity.personType",
                    "op": "eq",
                    "value": "user",
                },
            ]
        },
    }


def test_validate_slack_channel_history_access_probes_latest_message(
    monkeypatch,
) -> None:
    calls = []

    class FakeSlackClient:
        def __init__(self, access_token: str, team_id: str):
            calls.append(("init", access_token, team_id))

        async def get_conversation_history(self, *, channel: str, limit: int):
            calls.append(("history", channel, limit))
            return {"messages": []}

    monkeypatch.setattr(api, "SlackApiClientWrapper", FakeSlackClient)

    _validate_slack_channel_history_access(
        bot_access_token="xoxb-token",
        team_id="T123",
        channel_id="C123",
    )

    assert calls == [
        ("init", "xoxb-token", "T123"),
        ("history", "C123", 1),
    ]


def test_validate_slack_channel_history_access_rejects_slack_api_error(
    monkeypatch,
) -> None:
    class FakeSlackClient:
        def __init__(self, access_token: str, team_id: str):
            _ = access_token
            _ = team_id

        async def get_conversation_history(self, *, channel: str, limit: int):
            _ = channel
            _ = limit
            raise SlackConnectorApiError(
                "not in channel",
                metadata={"error": "not_in_channel"},
            )

    monkeypatch.setattr(api, "SlackApiClientWrapper", FakeSlackClient)

    with pytest.raises(HTTPException) as exc_info:
        _validate_slack_channel_history_access(
            bot_access_token="xoxb-token",
            team_id="T123",
            channel_id="C123",
        )

    assert exc_info.value.status_code == 400
    assert "not_in_channel" in exc_info.value.detail
