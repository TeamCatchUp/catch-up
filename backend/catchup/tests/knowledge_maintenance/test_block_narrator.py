"""블록 서술 어댑터가 무엇을 묻고 무엇을 실패로 다루는지 확인한다.

산문의 사실 입력은 statement뿐이다. 프롬프트에 문체·목적·인용이 실제로
실리는지, 그리고 빈 답이 조용히 통과하지 않는지를 fake LLM으로 본다.
"""

from __future__ import annotations

from typing import Any

import pytest
from structlog.testing import capture_logs

from catchup.knowledge_maintenance.adapters.llm import block_narrator
from catchup.knowledge_maintenance.adapters.llm.block_narrator import (
    EXPLAIN_PROMPT_VERSION,
)
from catchup.knowledge_maintenance.adapters.llm.block_narrator import PROMPT_VERSION
from catchup.knowledge_maintenance.adapters.llm.block_narrator import LlmBlockNarrator
from catchup.knowledge_maintenance.contracts.block_narration import ChangeReasonContract
from catchup.knowledge_maintenance.contracts.block_narration import NarrativeContract
from catchup.knowledge_maintenance.ports.narrator import ChangeExplanationRequest
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
    """with_structured_output만 흉내 내는 모델이다.

    계약마다 다른 구조화 출력을 돌려준다. 어댑터가 산문 계약과 변경 이유
    계약을 각각 따로 묶기 때문에, 하나로 뭉치면 어느 호출이 어느 프롬프트를
    받았는지 알 수 없다.
    """

    def __init__(
        self,
        response: Any = None,
        error: Exception | None = None,
        reason_response: Any = None,
        reason_error: Exception | None = None,
    ):
        self.structured = _FakeStructured(response, error)
        self.reason_structured = _FakeStructured(reason_response, reason_error)
        self.kwargs: dict[str, Any] = {}
        self.reason_kwargs: dict[str, Any] = {}

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        if schema is ChangeReasonContract:
            self.reason_kwargs = {"schema": schema, **kwargs}
            return self.reason_structured
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
    assert "Write 1 to 3 sentences" in rendered
    assert "No heading, no bullet list, no markdown." in rendered
    assert "Write in Korean." in rendered


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


def test_prompt_says_the_variant_list_may_be_partial() -> None:
    """후보 목록이 전부가 아닐 수 있음을 프롬프트가 못박는다.

    검증된 인용이 없는 후보는 요청에서 빠진다. 그 사실을 알리지 않으면
    모델이 남은 후보를 두고 갈린 값이 전부라고 셀 수 있다.
    """
    llm = _FakeLlm(_parsed("문장이다."))
    request = NarrationRequest(
        block_kind="contested",
        heading="rate_limit",
        topic_hint="상충하는 값 2개 — 검토 필요",
        statements=(),
        edges=(),
        variants=(("60", ("한도는 60이다",)),),
        style_instruction="담백하게 쓴다.",
        purpose_sentence="이 문서는 현황을 보는 데 쓴다.",
    )

    LlmBlockNarrator(llm).narrate(request)

    rendered = llm.structured.prompts[0]
    assert "The list may be partial" in rendered
    assert "candidates with no" in rendered
    assert "verified quote are left out" in rendered


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
    assert "(no direct quotes for this block)" in rendered
    # 관계 절은 인용이 없고 관계 줄만 사실 입력이다. 규칙 1이 인용만
    # 말하면 이 블록에서는 쓸 수 있는 사실이 하나도 없는 셈이 된다.
    assert (
        "State only what the quotes and relation lines above already say"
        in rendered
    )


def test_prompt_separates_wording_hints_from_facts() -> None:
    """원문 유래 문장은 사실이 아니라 표현 힌트 절에 실린다."""
    llm = _FakeLlm(_parsed("문장이다."))
    request = NarrationRequest(
        block_kind="relation_section",
        heading="requested_by(out)",
        topic_hint="requested_by(out)",
        statements=(),
        edges=("기능 요청 A → requested_by → 팀원A",),
        variants=(),
        style_instruction="담백하게 쓴다.",
        purpose_sentence="이 문서는 현황을 보는 데 쓴다.",
        hints=("커넥터 있어?",),
    )

    LlmBlockNarrator(llm).narrate(request)

    rendered = llm.structured.prompts[0]
    assert "## Wording hints (not facts)" in rendered
    assert "커넥터 있어?" in rendered
    assert "never add a party, a date or a number from them" in rendered
    assert "wording hints add no facts" in rendered


def test_prompt_omits_the_hint_section_without_hints() -> None:
    """힌트가 없으면 그 절 자체가 프롬프트에 서지 않는다."""
    llm = _FakeLlm(_parsed("문장이다."))

    LlmBlockNarrator(llm).narrate(_request())

    assert "## Wording hints (not facts)" not in llm.structured.prompts[0]


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


def test_contract_violation_logs_no_narrative() -> None:
    """파싱 예외 메시지에 실린 산문이 로그로 새지 않는다."""
    parsing_error = ValueError("이 요구는 아직 검토 중이다. 를 파싱하지 못했다")
    llm = _FakeLlm({"parsed": None, "parsing_error": parsing_error})

    with capture_logs() as logs:
        with pytest.raises(NarrationError):
            LlmBlockNarrator(llm).narrate(_request())

    dumped = str(logs)
    assert "이 요구는 아직 검토 중이다." not in dumped
    assert "파싱하지 못했다" not in dumped
    failed = next(
        entry for entry in logs if entry["event"] == "block_narration_failed"
    )
    assert failed["error_type"] == "ValueError"


def test_call_error_is_an_error() -> None:
    """호출 자체가 터져도 같은 예외로 감싼다."""
    llm = _FakeLlm(error=RuntimeError("연결 실패"))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate(_request())


def test_call_error_logs_no_statement_text() -> None:
    """호출 실패 로그에 예외 메시지와 인용 원문이 남지 않는다."""
    llm = _FakeLlm(error=RuntimeError("요청 거절: 상태는 검토 중이다"))

    with capture_logs() as logs:
        with pytest.raises(NarrationError):
            LlmBlockNarrator(llm).narrate(_request())

    dumped = str(logs)
    assert "상태는 검토 중이다" not in dumped
    assert "요청 거절" not in dumped
    failed = next(
        entry for entry in logs if entry["event"] == "block_narration_failed"
    )
    assert failed["error_type"] == "RuntimeError"
    assert failed["reason"] == "llm_call_error"


def test_prompt_render_error_is_a_narration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """프롬프트 렌더링이 터져도 같은 예외로 감싼다."""

    def _boom(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("렌더링 실패")

    monkeypatch.setattr(block_narrator.prompt_loader, "get_prompt", _boom)
    llm = _FakeLlm(_parsed("문장이다."))

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


def _parsed_reason(text: str) -> dict[str, Any]:
    """정상 변경 이유 구조화 출력 응답을 만든다."""
    return {
        "parsed": ChangeReasonContract(reason=text),
        "parsing_error": None,
    }


def _summary_request() -> NarrationRequest:
    """문서 머리말을 요청하는 요청 하나를 만든다."""
    return NarrationRequest(
        block_kind="summary",
        heading="기능 요청: CSV",
        topic_hint="요청 3건 (2026-08-15 관찰)",
        statements=("A사가 CSV 내보내기를 원한다",),
        edges=(),
        variants=(),
        style_instruction="보고서 요약 문단처럼 쓴다.",
        purpose_sentence="이 문서는 요구의 현황을 보는 데 쓴다.",
    )


def _change_request() -> ChangeExplanationRequest:
    """바뀐 블록 하나를 설명하는 요청을 만든다."""
    return ChangeExplanationRequest(
        heading="request_count",
        before_statements=("요청은 3회다",),
        after_statements=("요청은 4회다",),
        new_sources=("C사도 CSV 내보내기를 요청했다",),
        purpose_sentence="이 문서는 요구의 현황을 보는 데 쓴다.",
    )


def test_summary_request_renders_the_summary_branch() -> None:
    """summary 블록은 템플릿의 머리말 분기를 탄다."""
    llm = _FakeLlm(_parsed("**CSV 내보내기 요청이 늘었다**"))

    narrative = LlmBlockNarrator(llm).narrate(_summary_request())

    assert narrative == "**CSV 내보내기 요청이 늘었다**"
    rendered = llm.structured.prompts[0]
    assert "headline" in rendered.lower()
    assert "A사가 CSV 내보내기를 원한다" in rendered
    assert "보고서 요약 문단처럼 쓴다." in rendered


def test_summary_branch_replaces_the_paragraph_rules() -> None:
    """머리말 분기에서는 한 문단 규칙이 서지 않는다."""
    llm = _FakeLlm(_parsed("**헤드라인**"))

    LlmBlockNarrator(llm).narrate(_summary_request())

    rendered = llm.structured.prompts[0]
    assert "Write 1 to 3 sentences" not in rendered
    assert "Write in Korean." in rendered


def test_summary_empty_narrative_is_an_error() -> None:
    """머리말도 비면 실패다."""
    llm = _FakeLlm(_parsed("   "))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).narrate(_summary_request())


def test_explain_change_returns_the_reason() -> None:
    """변경 이유를 그대로 돌려준다."""
    llm = _FakeLlm(
        _parsed("문장이다."),
        reason_response=_parsed_reason("C사 요청이 더해져 횟수가 늘었다."),
    )

    reason = LlmBlockNarrator(llm).explain_change(_change_request())

    assert reason == "C사 요청이 더해져 횟수가 늘었다."


def test_explain_change_uses_function_calling_with_raw() -> None:
    """변경 이유도 같은 구조화 출력 관례를 쓴다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유다."))

    LlmBlockNarrator(llm)

    assert llm.reason_kwargs["schema"] is ChangeReasonContract
    assert llm.reason_kwargs["method"] == "function_calling"
    assert llm.reason_kwargs["include_raw"] is True


def test_explain_change_prompt_carries_before_after_and_sources() -> None:
    """이전·이후 문장과 새 인용이 프롬프트에 실린다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유다."))

    LlmBlockNarrator(llm).explain_change(_change_request())

    rendered = llm.reason_structured.prompts[0]
    assert "request_count" in rendered
    assert "요청은 3회다" in rendered
    assert "요청은 4회다" in rendered
    assert "C사도 CSV 내보내기를 요청했다" in rendered
    assert "이 문서는 요구의 현황을 보는 데 쓴다." in rendered
    assert "Write in Korean." in rendered
    assert "one sentence" in rendered.lower()


def test_explain_change_prompt_asks_for_the_polite_ending() -> None:
    """수정 이유 프롬프트는 존댓말 종결을 지시한다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유입니다."))

    LlmBlockNarrator(llm).explain_change(_change_request())

    rendered = llm.reason_structured.prompts[0]
    assert "-습니다" in rendered


def test_explain_change_prompt_carries_no_style_instruction() -> None:
    """문서 문체 preset은 수정 이유 프롬프트에 실리지 않는다."""
    llm = _FakeLlm(reason_response=_parsed_reason("이유입니다."))

    LlmBlockNarrator(llm).explain_change(_change_request())

    rendered = llm.reason_structured.prompts[0]
    assert "## Style" not in rendered


def test_explain_change_empty_reason_is_an_error() -> None:
    """빈 이유는 성공이 아니라 실패다."""
    llm = _FakeLlm(reason_response=_parsed_reason("   "))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_contract_violation_is_an_error() -> None:
    """구조화 출력이 깨지면 실패로 알린다."""
    llm = _FakeLlm(
        reason_response={"parsed": None, "parsing_error": ValueError("깨졌다")}
    )

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_call_error_is_an_error() -> None:
    """호출이 터져도 같은 예외로 감싼다."""
    llm = _FakeLlm(reason_error=RuntimeError("연결 실패"))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_prompt_render_error_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """프롬프트 렌더링이 터져도 같은 예외로 감싼다."""

    def _boom(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("렌더링 실패")

    monkeypatch.setattr(block_narrator.prompt_loader, "get_prompt", _boom)
    llm = _FakeLlm(reason_response=_parsed_reason("이유다."))

    with pytest.raises(NarrationError):
        LlmBlockNarrator(llm).explain_change(_change_request())


def test_explain_change_logs_carry_counts_and_no_content() -> None:
    """감사 로그에 판본과 개수만 남고 원문·이유는 남지 않는다."""
    llm = _FakeLlm(
        reason_response=_parsed_reason("C사 요청이 더해져 횟수가 늘었다.")
    )

    with capture_logs() as logs:
        LlmBlockNarrator(llm).explain_change(_change_request())

    events = [entry["event"] for entry in logs]
    assert "block_change_explanation_started" in events
    assert "block_change_explanation_completed" in events
    started = next(
        entry
        for entry in logs
        if entry["event"] == "block_change_explanation_started"
    )
    assert started["prompt_version"] == EXPLAIN_PROMPT_VERSION
    assert started["before_count"] == 1
    assert started["after_count"] == 1
    assert started["new_source_count"] == 1
    dumped = str(logs)
    assert "요청은 3회다" not in dumped
    assert "C사도 CSV 내보내기를 요청했다" not in dumped
    assert "C사 요청이 더해져 횟수가 늘었다." not in dumped


def test_explain_change_failure_logs_no_exception_message() -> None:
    """실패 로그에 예외 메시지와 원문이 남지 않는다."""
    llm = _FakeLlm(reason_error=RuntimeError("요청 거절: 요청은 3회다"))

    with capture_logs() as logs:
        with pytest.raises(NarrationError):
            LlmBlockNarrator(llm).explain_change(_change_request())

    dumped = str(logs)
    assert "요청은 3회다" not in dumped
    assert "요청 거절" not in dumped
    failed = next(
        entry
        for entry in logs
        if entry["event"] == "block_change_explanation_failed"
    )
    assert failed["error_type"] == "RuntimeError"
    assert failed["reason"] == "llm_call_error"
