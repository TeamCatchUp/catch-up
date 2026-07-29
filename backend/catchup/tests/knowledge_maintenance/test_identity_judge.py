from __future__ import annotations

import uuid

import pytest

from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    IdentityJudgeOutput,
)
from catchup.knowledge_maintenance.ports.identity_judge import JudgeCandidate


class _FakeStructured:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def ainvoke(self, rendered: str) -> dict:
        self.prompts.append(rendered)
        return self.response


class _FakeLlm:
    def __init__(self, response: dict) -> None:
        self.structured = _FakeStructured(response)

    def with_structured_output(self, *args, **kwargs):
        del args, kwargs
        return self.structured


def _group() -> tuple[JudgeCandidate, ...]:
    return (
        JudgeCandidate(
            candidate_id=uuid.uuid4(),
            proposed_type="platform",
            proposed_name="Slack",
            excerpt="Slack 연결이 끊겼습니다.",
        ),
        JudgeCandidate(
            candidate_id=uuid.uuid4(),
            proposed_type="integration",
            proposed_name="slack",
        ),
    )


def test_same_output_becomes_verdict() -> None:
    """구조화 출력이 IdentityVerdict로 바뀐다."""
    llm = _FakeLlm(
        {
            "parsed": IdentityJudgeOutput(
                same=True,
                reason="둘 다 Slack 연동을 가리킨다",
                canonical_type="integration",
                canonical_name="Slack",
            ),
            "raw": None,
        }
    )
    judge = BedrockIdentityJudge(llm)

    verdict = judge.judge(_group())

    assert verdict.same
    assert verdict.proposed_type == "integration"
    assert verdict.proposed_name == "Slack"
    rendered = llm.structured.prompts[0]
    assert "Slack" in rendered
    assert "Slack 연결이 끊겼습니다." in rendered


def test_parse_failure_raises() -> None:
    """계약 위반 출력은 예외로 올린다. 그룹 skip은 서비스의 몫이다."""
    llm = _FakeLlm({"parsed": None, "parsing_error": "invalid json"})
    judge = BedrockIdentityJudge(llm)

    with pytest.raises(ValueError):
        judge.judge(_group())
