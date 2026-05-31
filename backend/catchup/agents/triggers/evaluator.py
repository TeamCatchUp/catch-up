"""
AgentWebhookEvent가 Trigger Condition의 where clause를 만족하는지 평가
"""

from __future__ import annotations

from typing import Any

from catchup.agents.triggers.events import AgentWebhookEvent


class TriggerWhereEvaluationError(ValueError):
    """Trigger where clause를 안전하게 판정할 수 없을 때 발생"""


def evaluate_where_clause(where: dict[str, Any] | None, event: AgentWebhookEvent) -> bool:
    """
    저장된 policy.where를 webhook event에 적용
    """
    if not where:
        return True
    if "all" in where:
        clauses = _require_clause_list(where["all"])
        return all(_evaluate_clause(clause, event) for clause in clauses)
    if "any" in where:
        clauses = _require_clause_list(where["any"])
        return any(_evaluate_clause(clause, event) for clause in clauses)
    return _evaluate_clause(where, event)


def extract_path(event: AgentWebhookEvent, path: str) -> Any:
    if not path.startswith("$."):
        raise TriggerWhereEvaluationError(f"unsupported path: {path}")
    value: Any = event.model_dump(mode="python")
    for part in path[2:].split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
            continue
        raise TriggerWhereEvaluationError(f"path not found: {path}")
    return value


def _require_clause_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TriggerWhereEvaluationError("where clause group must be a list")
    for clause in value:
        if not isinstance(clause, dict):
            raise TriggerWhereEvaluationError("where clause must be an object")
    return value


def _evaluate_clause(clause: dict[str, Any], event: AgentWebhookEvent) -> bool:
    """단일 where clause 평가"""
    path = str(clause.get("path") or "")
    operator = str(clause.get("op") or "")
    if not path or not operator:
        raise TriggerWhereEvaluationError("where clause requires path and op")

    try:
        actual = extract_path(event, path)
    except TriggerWhereEvaluationError:
        if operator == "exists":
            return False
        raise

    expected = clause.get("value")
    if operator == "exists":
        return actual is not None
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    if operator == "in":
        if not isinstance(expected, list):
            raise TriggerWhereEvaluationError("in operator requires list value")
        return actual in expected
    if operator == "contains":
        return str(expected) in str(actual)
    if operator == "starts_with":
        return str(actual).startswith(str(expected))
    raise TriggerWhereEvaluationError(f"unsupported operator: {operator}")
