import pytest

from catchup.agents.triggers.policies import DebouncePolicy
from catchup.agents.triggers.policies import ImmediatePolicy
from catchup.agents.triggers.policies import PolicyValidationError
from catchup.agents.triggers.validator import TriggerPolicyValidator
from catchup.agents.triggers.validator import trigger_policy_validator


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
                    "path": "$.payload.entity.personType",
                    "op": "eq",
                    "value": "user",
                },
            ],
        },
    }
    policy.update(overrides)
    return policy


def test_trigger_policy_validator_can_be_instantiated() -> None:
    validator = TriggerPolicyValidator()

    assert isinstance(validator, TriggerPolicyValidator)


def test_trigger_policy_validator_accepts_immediate_policy() -> None:
    policy = trigger_policy_validator.validate_policy(
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


def test_trigger_policy_validator_accepts_debounce_policy_without_condition_version() -> None:
    policy = trigger_policy_validator.validate_policy(_debounce_policy())

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
def test_trigger_policy_validator_rejects_unsupported_or_malformed_policy(
    condition,
) -> None:
    with pytest.raises(PolicyValidationError):
        trigger_policy_validator.validate_policy(condition)
