import pytest

from catchup.agents.triggers.policies import DebouncePolicy
from catchup.agents.triggers.policies import ImmediatePolicy
from catchup.agents.triggers.policies import PolicyValidationError
from catchup.agents.triggers.policies import parse_policy


def _debounce_policy(**overrides):
    policy = {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": 300,
        "run_context": "latest_event",
        "where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "ch-001",
                },
            ],
        },
        "reset_where": {
            "all": [
                {
                    "path": "$.payload.entity.chatType",
                    "op": "eq",
                    "value": "userChat",
                },
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "ch-001",
                },
            ],
        },
    }
    policy.update(overrides)
    return policy


def test_parse_policy_reports_validation_errors_with_domain_exception() -> None:
    with pytest.raises(PolicyValidationError):
        parse_policy({"kind": "immediate", "unexpected": True})


def test_parse_policy_accepts_immediate_policy() -> None:
    policy = parse_policy(
        {
            "kind": "immediate",
            "where": {
                "all": [
                    {
                        "path": "$.event_type",
                        "op": "eq",
                        "value": "user_chat.created",
                    },
                ],
            },
        },
    )

    assert isinstance(policy, ImmediatePolicy)
    assert policy.where["all"][0]["path"] == "$.event_type"


def test_parse_policy_accepts_debounce_policy_without_condition_version() -> None:
    policy = parse_policy(_debounce_policy())

    assert isinstance(policy, DebouncePolicy)
    assert policy.start_event_type == "user_chat.created"
    assert policy.reset_event_types == ("user_chat.new_message",)
    assert policy.quiet_period_seconds == 300
    assert policy.model_dump(mode="json")["reset_event_types"] == [
        "user_chat.new_message",
    ]


@pytest.mark.parametrize(
    "condition",
    [
        {"kind": "threshold"},
        {},
        {"where": {"all": []}},
        _debounce_policy(start_event_type=None),
        _debounce_policy(reset_event_types=None),
        _debounce_policy(entity_key_path=None),
        _debounce_policy(reset_entity_key_path=None),
        _debounce_policy(quiet_period_seconds=0),
        _debounce_policy(quiet_period_seconds=-1),
        _debounce_policy(quiet_period_seconds=True),
        _debounce_policy(extra_field="not allowed"),
    ],
)
def test_parse_policy_rejects_unsupported_or_malformed_policy(
    condition,
) -> None:
    with pytest.raises(PolicyValidationError):
        parse_policy(condition)
