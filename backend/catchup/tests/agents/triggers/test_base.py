from catchup.agents.triggers.base import EventSource
from catchup.agents.triggers.base import EventSpec
from catchup.agents.triggers.base import FilterFieldSpec
from catchup.agents.triggers.policies import ImmediatePolicy
from catchup.agents.triggers.validator import trigger_policy_validator


def test_event_spec_schema_exposes_policy_clause_building_fields() -> None:
    event = EventSpec(
        type="user_chat.message_created",
        description="유저 채팅방에 새 메시지가 생성됨",
        filterable_fields={
            "channel_id": FilterFieldSpec(
                path="$.payload.entity.channelId",
                type="string",
                description="메시지가 발생한 채널 ID",
                operators=["eq", "in"],
                examples=["ch-001"],
            ),
        },
    )

    schema = event.schema_dict()

    assert schema["filterable_fields"]["channel_id"] == {
        "path": "$.payload.entity.channelId",
        "type": "string",
        "description": "메시지가 발생한 채널 ID",
        "operators": ["eq", "in"],
        "examples": ["ch-001"],
    }


def test_filter_field_spec_builds_clause_accepted_by_policy_validator() -> None:
    channel_id = FilterFieldSpec(
        path="$.payload.entity.channelId",
        type="string",
        description="메시지가 발생한 채널 ID",
        operators=["eq", "in"],
    )

    policy = trigger_policy_validator.validate_policy(
        {
            "kind": "immediate",
            "where": {
                "all": [
                    channel_id.condition_clause("ch-001"),
                ],
            },
        },
    )

    assert isinstance(policy, ImmediatePolicy)
    assert policy.where["all"][0] == {
        "path": "$.payload.entity.channelId",
        "op": "eq",
        "value": "ch-001",
    }


def test_event_source_schema_wraps_event_filter_specs() -> None:
    class ChannelTalkEventSource(EventSource):
        name = "channel_talk"
        display_name = "Channel Talk"
        supported_events = [
            EventSpec(
                type="user_chat.message_created",
                description="유저 채팅방에 새 메시지가 생성됨",
                filterable_fields={
                    "person_type": FilterFieldSpec(
                        path="$.payload.entity.personType",
                        type="string",
                        description="메시지 작성자 유형",
                        operators=["eq"],
                        examples=["user"],
                    ),
                },
            ),
        ]

    schema = ChannelTalkEventSource().schema()

    assert schema["display_name"] == "Channel Talk"
    assert schema["events"]["user_chat.message_created"]["filterable_fields"][
        "person_type"
    ]["path"] == "$.payload.entity.personType"
