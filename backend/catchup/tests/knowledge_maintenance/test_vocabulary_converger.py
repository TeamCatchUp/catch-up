from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ConnectionClosedError

from catchup.knowledge_maintenance.adapters.llm import retry as llm_retry
from catchup.knowledge_maintenance.adapters.llm.retry import LlmRetryPolicy
from catchup.knowledge_maintenance.adapters.llm.vocabulary_converger import (
    TEMPLATE_PATH,
)
from catchup.knowledge_maintenance.adapters.llm.vocabulary_converger import (
    LlmVocabularyConverger,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    PredicateUsage,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    ProposedPredicateEntry,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import RelationUsage
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    SynonymAbsorption,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    VocabularyConvergenceProposal,
)
from catchup.prompts.loader import prompt_loader

_NO_WAIT_RETRY_POLICY = LlmRetryPolicy(base_delay=0.0, max_delay=0.0)


class _StubStructuredRunnable:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.rendered_prompt: str | None = None

    async def ainvoke(self, prompt: str) -> dict[str, Any]:
        self.rendered_prompt = prompt
        return self._response


class _FakeLlm:
    """with_structured_output만 흉내내는 최소 대역이다."""

    def __init__(
        self,
        *,
        parsed: VocabularyConvergenceProposal | None = None,
        parsing_error: str | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.runnable = _StubStructuredRunnable(
            {"parsed": parsed, "raw": None, "parsing_error": parsing_error}
        )
        self._raises = raises
        self.structured_output_kwargs: dict[str, Any] = {}

    def with_structured_output(self, *args: Any, **kwargs: Any):
        self.structured_output_kwargs = kwargs
        if self._raises is not None:
            raise_error = self._raises

            class _Boom:
                async def ainvoke(self, prompt: str) -> dict[str, Any]:
                    raise raise_error

            return _Boom()
        return self.runnable


class _SequenceStructuredRunnable:
    """호출마다 정해진 응답을 차례로 돌려주는 대역이다.

    응답이 예외면 던진다. 재시도가 실제로 두 번째 호출을 하는지 보려면
    호출 횟수를 세야 한다.
    """

    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self._responses = responses
        self.call_count = 0

    async def ainvoke(self, prompt: str) -> dict[str, Any]:
        response = self._responses[self.call_count]
        self.call_count += 1
        if isinstance(response, Exception):
            raise response
        return response


class _SequenceLlm:
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.runnable = _SequenceStructuredRunnable(responses)

    def with_structured_output(self, *args: Any, **kwargs: Any):
        return self.runnable


def _current_vocabulary() -> ExtractionVocabulary:
    return ExtractionVocabulary(
        predicate_entries=(
            PredicateEntry(
                name="deployment_scheduled_on",
                definition="배포가 예정된 날짜다.",
                value_type="date",
                domain=("feature",),
            ),
        ),
        relation_type_entries=(
            RelationTypeEntry(
                name="depends_on",
                definition="앞의 대상이 뒤의 대상에 의존한다.",
                domain=("feature",),
                range_=("system",),
            ),
        ),
    )


def _usage(name: str) -> PredicateUsage:
    return PredicateUsage(
        name=name,
        usage_count=4,
        value_types=("date",),
        observed_values=("2026-08-12", "2026-09-01"),
        example_statements=("결제 기능은 8월 12일 배포 예정이다.",),
        subject_types=("feature",),
    )


def _relation_usage(name: str) -> RelationUsage:
    return RelationUsage(
        name=name,
        usage_count=2,
        example_assertions=("payment_feature --blocked_by--> auth_system",),
    )


class TestPromptRendering:
    def test_현행_사전과_OOV_현황이_프롬프트에_실린다(self) -> None:
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            current=_current_vocabulary(),
            predicate_usage=[_usage("expected_release_date")],
            relation_usage=[],
        )

        assert "deployment_scheduled_on" in rendered
        assert "depends_on" in rendered
        assert "expected_release_date" in rendered
        assert "2026-08-12" in rendered
        assert "used 4 times" in rendered
        assert "feature" in rendered
        assert "결제 기능은 8월 12일 배포 예정이다." in rendered

    def test_빈_사전도_렌더된다(self) -> None:
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("p")],
            relation_usage=[],
        )

        assert "no predicate entries" in rendered
        assert "no relation type entries" in rendered

    def test_관계_현황도_프롬프트에_실린다(self) -> None:
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            current=_current_vocabulary(),
            predicate_usage=[],
            relation_usage=[_relation_usage("blocked_by")],
        )

        assert "blocked_by" in rendered
        assert "used 2 times" in rendered

    def test_수렴_규칙_여섯_가지가_모두_실린다(self) -> None:
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("p")],
            relation_usage=[],
        )

        # Rule 1: 기존 항목과 같은 뜻이면 흡수한다.
        assert "absorption" in rendered
        # Rule 2: 서로 동의어면 하나의 정본 이름으로 모은다.
        assert "source_candidates" in rendered
        # Rule 3: 새 항목의 필수 요소. source_candidates는 모든 항목에
        # 필수다 — 비면 가드의 관측 증거 검사에서 떨어진다.
        assert "EVERY new entry needs `source_candidates`" in rendered
        assert "verbatim as observed" in rendered
        assert "배포예정일" in rendered
        assert "value_type" in rendered
        assert "enum_values" in rendered
        assert "number|date|boolean|enum|text" in rendered
        # Rule 4: 기존 항목 재정의 금지.
        assert "Never redefine" in rendered
        # Rule 5: lower snake_case 영어 이름.
        assert "snake_case" in rendered
        # Rule 6: 모든 판정에 이유를 붙인다.
        assert "reason" in rendered
        assert "audit" in rendered


class TestLlmVocabularyConverger:
    @pytest.mark.asyncio
    async def test_구조화_출력을_그대로_돌려준다(self) -> None:
        proposal = VocabularyConvergenceProposal(
            absorptions=(
                SynonymAbsorption(
                    candidate_name="expected_release_date",
                    canonical_name="deployment_scheduled_on",
                    reason="같은 날짜를 가리킨다.",
                ),
            ),
            predicate_entries=(
                ProposedPredicateEntry(
                    name="release_channel",
                    definition="배포 채널이다.",
                    value_type="enum",
                    enum_values=("beta", "ga"),
                    source_candidates=("release_channel",),
                    reason="관측 값이 두 종류로 닫힌다.",
                ),
            ),
        )
        llm = _FakeLlm(parsed=proposal)
        converger = LlmVocabularyConverger(llm)

        result = await converger.propose(
            current=_current_vocabulary(),
            predicate_usage=[_usage("expected_release_date")],
            relation_usage=[],
        )

        assert result == proposal
        assert llm.structured_output_kwargs["method"] == "function_calling"
        assert llm.structured_output_kwargs["include_raw"] is True
        assert "expected_release_date" in (llm.runnable.rendered_prompt or "")

    @pytest.mark.asyncio
    async def test_파싱_실패는_None을_돌려준다(self) -> None:
        converger = LlmVocabularyConverger(
            _FakeLlm(parsed=None, parsing_error="schema mismatch")
        )

        result = await converger.propose(
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("p")],
            relation_usage=[],
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_호출_예외도_None을_돌려준다(self) -> None:
        converger = LlmVocabularyConverger(
            _FakeLlm(raises=RuntimeError("upstream down"))
        )

        result = await converger.propose(
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("p")],
            relation_usage=[_relation_usage("blocked_by")],
        )

        assert result is None


class TestRetry:
    """실패 한 번은 재시도로 덮고, 두 번이면 포기한다."""

    def _proposal(self) -> VocabularyConvergenceProposal:
        return VocabularyConvergenceProposal(
            predicate_entries=(
                ProposedPredicateEntry(
                    name="release_date",
                    definition="배포 날짜다.",
                    value_type="date",
                    source_candidates=("release_date",),
                    reason="관측이 날짜로 닫힌다.",
                ),
            ),
        )

    @pytest.mark.asyncio
    async def test_한_번_실패해도_재시도로_제안을_받는다(self) -> None:
        proposal = self._proposal()
        llm = _SequenceLlm(
            [
                RuntimeError("upstream down"),
                {"parsed": proposal, "raw": None, "parsing_error": None},
            ]
        )
        converger = LlmVocabularyConverger(llm)

        result = await converger.propose(
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("release_date")],
            relation_usage=[],
        )

        assert result == proposal
        assert llm.runnable.call_count == 2

    @pytest.mark.asyncio
    async def test_파싱_실패도_재시도한다(self) -> None:
        proposal = self._proposal()
        llm = _SequenceLlm(
            [
                {"parsed": None, "raw": None, "parsing_error": "schema mismatch"},
                {"parsed": proposal, "raw": None, "parsing_error": None},
            ]
        )
        converger = LlmVocabularyConverger(llm)

        result = await converger.propose(
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("release_date")],
            relation_usage=[],
        )

        assert result == proposal
        assert llm.runnable.call_count == 2

    @pytest.mark.asyncio
    async def test_두_번_실패하면_None이고_더_조르지_않는다(self) -> None:
        llm = _SequenceLlm(
            [
                RuntimeError("upstream down"),
                {"parsed": None, "raw": None, "parsing_error": "schema mismatch"},
            ]
        )
        converger = LlmVocabularyConverger(llm)

        result = await converger.propose(
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("release_date")],
            relation_usage=[],
        )

        assert result is None
        assert llm.runnable.call_count == 2

    @pytest.mark.asyncio
    async def test_연결이_끊기면_같은_시도_안에서_다시_부른다(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """일시적 연결 끊김은 어댑터의 시도 횟수를 쓰지 않고 재시도한다."""
        monkeypatch.setattr(
            llm_retry, "DEFAULT_LLM_RETRY_POLICY", _NO_WAIT_RETRY_POLICY
        )
        proposal = self._proposal()
        llm = _SequenceLlm(
            [
                ConnectionClosedError(endpoint_url="https://bedrock"),
                ConnectionClosedError(endpoint_url="https://bedrock"),
                {"parsed": proposal, "raw": None, "parsing_error": None},
            ]
        )
        converger = LlmVocabularyConverger(llm)

        result = await converger.propose(
            current=ExtractionVocabulary(),
            predicate_usage=[_usage("release_date")],
            relation_usage=[],
        )

        assert result == proposal
        assert llm.runnable.call_count == 3
