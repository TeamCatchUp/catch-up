from __future__ import annotations

import uuid

import pytest
from botocore.exceptions import ConnectionClosedError

from catchup.knowledge_maintenance.adapters.llm import retry as llm_retry
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    IdentityJudgeOutput,
)
from catchup.knowledge_maintenance.adapters.llm.retry import LlmRetryPolicy
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.ports.identity_judge import JudgeCandidate

_NO_WAIT_RETRY_POLICY = LlmRetryPolicy(base_delay=0.0, max_delay=0.0)


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


def _verdict_llm() -> _FakeLlm:
    return _FakeLlm(
        {
            "parsed": IdentityJudgeOutput(same=False, reason="근거 부족"),
            "raw": None,
        }
    )


def test_anchored_types_enter_the_prompt() -> None:
    """anchored로 선언한 종류만 판정 규칙으로 렌더된다."""
    llm = _verdict_llm()
    judge = BedrockIdentityJudge(
        llm,
        entity_types=(
            EntityTypeEntry(
                name="team",
                definition="A working group inside one organization.",
                identity_scope="anchored",
            ),
            EntityTypeEntry(
                name="product",
                definition="A product named the same everywhere.",
                identity_scope="standalone",
            ),
        ),
    )

    judge.judge(_group())

    rendered = llm.structured.prompts[0]
    assert "anchored" in rendered
    assert "team — A working group inside one organization." in rendered
    assert "A product named the same everywhere." not in rendered


def test_empty_dictionary_drops_the_anchored_rule() -> None:
    """사전이 비면 규칙이 통째로 빠진다. 빈 목록만 남기지 않는다."""
    llm = _verdict_llm()
    judge = BedrockIdentityJudge(llm)

    judge.judge(_group())

    assert "anchored" not in llm.structured.prompts[0]


def test_parse_failure_raises() -> None:
    """계약 위반 출력은 예외로 올린다. 그룹 skip은 서비스의 몫이다."""
    llm = _FakeLlm({"parsed": None, "parsing_error": "invalid json"})
    judge = BedrockIdentityJudge(llm)

    with pytest.raises(ValueError):
        judge.judge(_group())


class _FlakyStructured:
    """첫 호출만 연결 끊김으로 실패하고 다음 호출부터 정상 응답을 준다."""

    def __init__(self, response: dict, error: Exception) -> None:
        self.response = response
        self._pending_error: Exception | None = error
        self.call_count = 0

    async def ainvoke(self, rendered: str) -> dict:
        self.call_count += 1
        if self._pending_error is not None:
            error, self._pending_error = self._pending_error, None
            raise error
        return self.response


class _FlakyLlm:
    def __init__(self, response: dict, error: Exception) -> None:
        self.structured = _FlakyStructured(response, error)

    def with_structured_output(self, *args, **kwargs):
        del args, kwargs
        return self.structured


def test_judge_retries_transient_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """판정 호출이 끊기면 다시 불러 판정을 받아 온다."""
    monkeypatch.setattr(llm_retry, "DEFAULT_LLM_RETRY_POLICY", _NO_WAIT_RETRY_POLICY)
    llm = _FlakyLlm(
        {
            "parsed": IdentityJudgeOutput(
                same=True,
                reason="같은 대상이다",
                canonical_type="integration",
                canonical_name="Slack",
            ),
            "raw": None,
        },
        ConnectionClosedError(endpoint_url="https://bedrock"),
    )

    verdict = BedrockIdentityJudge(llm).judge(_group())

    assert verdict.same
    assert llm.structured.call_count == 2
