"""블록 서술 어댑터가 무엇을 묻고 무엇을 실패로 다루는지 확인한다.

산문의 사실 입력은 statement뿐이다. 프롬프트에 문체·목적·인용이 실제로
실리는지, 그리고 빈 답이 조용히 통과하지 않는지를 fake LLM으로 본다.
"""

from __future__ import annotations

from typing import Any

import pytest
from structlog.testing import capture_logs

from catchup.knowledge_maintenance.adapters.llm.block_narrator import PROMPT_VERSION
from catchup.knowledge_maintenance.adapters.llm.block_narrator import LlmBlockNarrator
from catchup.knowledge_maintenance.contracts.block_narration import NarrativeContract
from catchup.knowledge_maintenance.ports.narrator import NarrationError
from catchup.knowledge_maintenance.ports.narrator import NarrationRequest


class _FakeStructured:
    """구조화 출력을 흉내 내고 받은 프롬프트를 기록한다."""

    def __init__(self, response: Any, error: Exception | None) -> None:
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    def invoke(self, rendered: str) -> Any:
        self.prompts.append(rendered)
        if self.error is not None:
            raise self.error
        return self.response


class _FakeLlm:
    """with_structured_output만 흉내 내는 모델이다."""

    def __init__(self, response: Any = None, error: Exception | None = None):
        self.structured = _FakeStructured(response, error)
        self.kwargs: dict[str, Any] = {}

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        self.kwargs = {"schema": schema, **kwargs}
        return self.structured


def _parsed(text: str) -> dict[str, Any]:
    """정상 구조화 출력 응답을 만든다."""
    return {
        "parsed": NarrativeContract(narrative=text),
        "parsing_error": None,
    }


def _request() -> NarrationRequest:
    """문체·목적·인용이 모두 실린 요청 하나를 만든다."""
    return NarrationRequest(
        block_kind="claim_section",
        heading="request_status",
        topic_hint="검토 중 (2026-08-15 관찰)",
        statements=("상태는 검토 중이다", "담당은 아직 정해지지 않았다"),
        edges=(),
        variants=(),
        style_instruction="보고서 요약 문단처럼 쓴다.",
        purpose_sentence="이 문서는 요구의 현황을 보는 데 쓴다.",
    )


def test_returns_the_narrative() -> None:
    """구조화 출력의 산문을 그대로 돌려준다."""
    llm = _FakeLlm(_parsed("이 요구는 아직 검토 중이다."))

    narrative = LlmBlockNarrator(llm).narrate(_request())

    assert narrative == "이 요구는 아직 검토 중이다."


def test_uses_function_calling_with_raw() -> None:
    """구조화 출력 호출 관례가 어휘 수렴 어댑터와 같다."""
    llm = _FakeLlm(_parsed("문장이다."))

    LlmBlockNarrator(llm)

    assert llm.kwargs["schema"] is NarrativeContract
    assert llm.kwargs["method"] == "function_calling"
    assert llm.kwargs["include_raw"] is True


def test_prompt_carries_style_purpose_and_statements() -> None:
    """문체·목적·인용이 프롬프트에 실제로 실린다."""
    llm = _FakeLlm(_parsed("문장이다."))

    LlmBlockNarrator(llm).narrate(_request())

    rendered = llm.structured.prompts[0]
    assert "보고서 요약 문단처럼 쓴다." in rendered
    assert "이 문서는 요구의 현황을 보는 데 쓴다." in rendered
    assert "상태는 검토 중이다" in rendered
    assert "담당은 아직 정해지지 않았다" in rendered
    assert "request_status" in rendered


def test_prompt_marks_the_topic_hint_as_a_hint() -> None:
    """주제 힌트가 근거가 아님을 프롬프트가 못박는다."""
    llm = _FakeLlm(_parsed("문장이다."))

    LlmBlockNarrator(llm).narrate(_request())

    rendered = llm.structured.prompts[0]
    assert "hints only" in rendered
    assert "검토 중 (2026-08-15 관찰)" in rendered


def test_prompt_keeps_variants_apart() -> None:
    """대조 후보는 후보별 인용과 함께 갈라져 실린다."""
    llm = _FakeLlm(_parsed("문장이다."))
    request = NarrationRequest(
        block_kind="contested",
        heading="rate_limit",
        topic_hint="상충하는 값 2개 — 검토 필요",
        statements=(),
        edges=(),
        variants=(
            ("60", ("한도는 60이다",)),
            ("120", ("한도는 120이다",)),
        ),
        style_instruction="담백하게 쓴다.",
        purpose_sentence="이 문서는 현황을 보는 데 쓴다.",
    )

    LlmBlockNarrator(llm).narrate(request)

    rendered = llm.structured.prompts[0]
    assert "한도는 60이다" in rendered
    assert "한도는 120이다" in rendered
    assert "do not judge" in rendered


def test_prompt_lists_relation_edges() -> None:
    """관계 절의 본문 줄이 그래프 사실로 프롬프트에 실린다."""
    llm = _FakeLlm(_parsed("문장이다."))
    request = NarrationRequest(
        block_kind="relation_section",
        heading="requested_by(out)",
        topic_hint="requested_by(out)",
        statements=(),
        edges=(
            "A사가 이 기능을 요청했다",
            "(step 0에서 이웃 50개 상한 초과 — 일부만 따라감)",
        ),
        variants=(),
        style_instruction="담백하게 쓴다.",
        purpose_sentence="이 문서는 현황을 보는 데 쓴다.",
    )

    LlmBlockNarrator(llm).narrate(request)

    rendered = llm.structured.prompts[0]
    assert "Relations (graph facts)" in rendered
    assert "A사가 이 기능을 요청했다" in rendered
    assert "일부만 따라감" in rendered
    assert "never infer another connection" in rendered


def test_empty_narrative_is_an_error() -> None:
    """빈 산문은 성공이 아니라 실패다."""
    llm = _FakeLlm(_parsed("   "))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate(_request())


def test_contract_violation_is_an_error() -> None:
    """구조화 출력이 깨지면 실패로 알린다."""
    llm = _FakeLlm({"parsed": None, "parsing_error": ValueError("깨졌다")})

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate(_request())


def test_call_error_is_an_error() -> None:
    """호출 자체가 터져도 같은 예외로 감싼다."""
    llm = _FakeLlm(error=RuntimeError("연결 실패"))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate(_request())


def test_logs_carry_prompt_version_and_no_content() -> None:
    """감사 로그에 판본은 남고 원문·산문은 남지 않는다."""
    llm = _FakeLlm(_parsed("이 요구는 아직 검토 중이다."))

    with capture_logs() as logs:
        LlmBlockNarrator(llm).narrate(_request())

    events = [entry["event"] for entry in logs]
    assert "block_narration_started" in events
    assert "block_narration_completed" in events
    started = next(
        entry for entry in logs if entry["event"] == "block_narration_started"
    )
    assert started["prompt_version"] == PROMPT_VERSION
    assert started["block_kind"] == "claim_section"
    assert started["statement_count"] == 2
    dumped = str(logs)
    assert "상태는 검토 중이다" not in dumped
    assert "이 요구는 아직 검토 중이다." not in dumped
