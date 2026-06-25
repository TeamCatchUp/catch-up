import pytest

from catchup.agents.triggers.evaluator import TriggerWhereEvaluationError
from catchup.agents.triggers.evaluator import evaluate_where_clause
from catchup.agents.triggers.events import AgentWebhookEvent


def _event() -> AgentWebhookEvent:
    return AgentWebhookEvent(
        event_id="evt",
        source="channel_talk",
        event_type="user_chat.new_message",
        payload={
            "tags": ["vip", "trial"],
            "entity": {
                "channelId": "ch-001",
                "body": "hello world",
            },
        },
    )


@pytest.mark.parametrize(
    "clause",
    [
        {"path": "$.payload.entity.channelId", "op": "eq", "value": "ch-001"},
        {"path": "$.payload.entity.channelId", "op": "neq", "value": "ch-002"},
        {"path": "$.event_type", "op": "in", "value": ["user_chat.new_message"]},
        {"path": "$.payload.entity.body", "op": "contains", "value": "world"},
        {"path": "$.payload.entity.channelId", "op": "starts_with", "value": "ch-"},
        {"path": "$.payload.entity.channelId", "op": "exists"},
    ],
)
def test_evaluate_where_clause_supports_v0_operators(clause) -> None:
    assert evaluate_where_clause({"all": [clause]}, _event()) is True


def test_evaluate_where_clause_returns_false_for_missing_exists_path() -> None:
    assert (
        evaluate_where_clause(
            {"path": "$.payload.missing", "op": "exists"},
            _event(),
        )
        is False
    )


def test_evaluate_where_clause_rejects_unknown_operator() -> None:
    with pytest.raises(TriggerWhereEvaluationError):
        evaluate_where_clause(
            {"path": "$.payload.entity.channelId", "op": "regex", "value": ".*"},
            _event(),
        )
