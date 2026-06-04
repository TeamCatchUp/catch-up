import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.server.agents import build
from catchup.server.agents.build import PRESET_KEY
from catchup.server.agents.build import SLACK_FIND_TOOL_NAME
from catchup.server.agents.build import SLACK_SEND_TOOL_NAME
from catchup.server.agents.build import TempAgentPublishRequest
from catchup.server.agents.build import _build_channel_talk_debounce_condition
from catchup.server.agents.build import _build_preset_agent_id
from catchup.server.agents.build import _build_preset_agent_spec
from catchup.server.agents.build import _build_references
from catchup.server.agents.build import _validate_slack_channel_history_access


def test_temp_agent_publish_request_requires_slack_channel() -> None:
    with pytest.raises(ValidationError):
        TempAgentPublishRequest.model_validate(
            {
                "channel_talk_credential_id": 7,
                "quiet_period_seconds": 60,
            }
        )


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


def test_build_references_materializes_required_slack_values() -> None:
    references = _build_references(
        slack_reference={
            "channel_name": "cs-alerts",
            "channel_id": "C123",
            "credential_id": 42,
        },
    )

    for tool_name in (SLACK_FIND_TOOL_NAME, SLACK_SEND_TOOL_NAME):
        assert references[tool_name] == [
            {
                "argument": "channel_name",
                "kind": "slack_channel",
                "values": {
                    "cs-alerts": {
                        "channel_id": "C123",
                        "credential_id": 42,
                    }
                },
            }
        ]


def test_build_preset_agent_spec_contains_tools_order_and_references() -> None:
    references = _build_references(
        slack_reference={
            "channel_name": "cs-alerts",
            "channel_id": "C123",
            "credential_id": 42,
        },
    )

    spec = _build_preset_agent_spec(references=references)

    assert spec.agent_id == PRESET_KEY
    assert [tool.name for tool in spec.tools] == [
        "catchup_kb.search",
        "catchup_kb.rerank",
        SLACK_FIND_TOOL_NAME,
        SLACK_SEND_TOOL_NAME,
    ]
    assert spec.execution_order == [
        "catchup_kb.search",
        "catchup_kb.rerank",
        SLACK_FIND_TOOL_NAME,
        SLACK_SEND_TOOL_NAME,
    ]
    assert spec.model_dump(mode="json")["references"] == references


def test_build_preset_agent_id_is_stable_for_idempotency_key() -> None:
    first = _build_preset_agent_id(
        workspace_id=1,
        preset_key=PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )
    second = _build_preset_agent_id(
        workspace_id=1,
        preset_key=PRESET_KEY,
        channel_talk_channel_id="229395",
        slack_channel_id="C123",
    )

    assert first == second


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

    monkeypatch.setattr(build, "SlackApiClientWrapper", FakeSlackClient)

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

    monkeypatch.setattr(build, "SlackApiClientWrapper", FakeSlackClient)

    with pytest.raises(HTTPException) as exc_info:
        _validate_slack_channel_history_access(
            bot_access_token="xoxb-token",
            team_id="T123",
            channel_id="C123",
        )

    assert exc_info.value.status_code == 400
    assert "not_in_channel" in exc_info.value.detail
