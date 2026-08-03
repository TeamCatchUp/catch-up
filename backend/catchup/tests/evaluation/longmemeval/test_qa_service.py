"""LongMemEval QA 러너의 순수 로직이 fail-closed인지 검증한다.

지키는 선은 셋이다. 하나, subject가 하나도 걸리지 않으면 답변 LLM을
아예 부르지 않고 고정 abstention 문구를 쓴다 — 재료 없이 모델이 지어낸
문장은 벤치마크 점수를 부풀리기만 한다. 둘, 컨텍스트에는 언제부터
언제까지 참이었는지가 반드시 실린다. 셋, trace는 그 판단을 되짚을 수
있을 만큼 채워진다.

DB도 LLM도 부르지 않는다. 조회와 모델 자리에 고정 응답 fake만 넣는다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone

from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.qa_service import ABSTENTION_ANSWER
from catchup.evaluation.longmemeval.qa_service import MAX_SUBJECTS
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import UsageTotals
from catchup.evaluation.longmemeval.qa_service import answer_questions
from catchup.evaluation.longmemeval.qa_service import build_answer_prompt
from catchup.evaluation.longmemeval.qa_service import render_claims_context
from catchup.evaluation.longmemeval.qa_service import run_question
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import MatchedSubject

QUESTION_DATE = datetime(2023, 6, 1, tzinfo=timezone.utc)


def _question(question_id: str = "q1") -> OracleQuestion:
    """평가 문항 하나를 만든다."""
    return OracleQuestion(
        question_id=question_id,
        question_type="knowledge-update",
        question="Where does Alice work now?",
        answer="Acme",
        question_date=QUESTION_DATE,
        sessions=(),
        answer_session_ids=frozenset(),
    )


def _claim(
    predicate: str = "employer",
    value: str = "Acme",
    valid_from: datetime | None = datetime(2023, 1, 1, tzinfo=timezone.utc),
    valid_to: datetime | None = None,
) -> AsOfClaim:
    """claim 한 건을 만든다."""
    return AsOfClaim(
        claim_id=uuid.uuid4(),
        predicate=predicate,
        value_type="text",
        value=value,
        statement=f"Alice works at {value}.",
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _matched(display_name: str = "Alice") -> MatchedSubject:
    """매칭된 대상 하나를 만든다."""
    return MatchedSubject(
        node_id=uuid.uuid4(),
        entity_type="person",
        display_name=display_name,
        matched_by="canonical_key",
    )


def _hit(*claims: AsOfClaim) -> AsOfQueryResult:
    """대상을 찾은 조회 결과를 만든다."""
    return AsOfQueryResult(
        subject=_matched(),
        as_of=QUESTION_DATE,
        claims=tuple(claims),
    )


def _miss() -> AsOfQueryResult:
    """대상을 못 찾은 조회 결과를 만든다."""
    return AsOfQueryResult(subject=None, as_of=QUESTION_DATE, claims=())


def _lookup(
    as_of: dict[str, AsOfQueryResult] | None = None,
    history: dict[str, AsOfQueryResult] | None = None,
) -> KnowledgeLookup:
    """subject별 고정 응답을 돌려주는 fake 조회를 만든다."""
    as_of_map = as_of or {}
    history_map = history or {}
    return KnowledgeLookup(
        as_of=lambda subject, at: as_of_map.get(subject, _miss()),
        history=lambda subject: history_map.get(subject, _miss()),
    )


class _FakeExtract:
    """고정 subject 후보를 돌려주는 fake 추출기다."""

    def __init__(self, subjects: tuple[str, ...]) -> None:
        self.subjects = subjects
        self.calls: list[str] = []

    def __call__(self, question: str) -> SubjectResult:
        self.calls.append(question)
        return SubjectResult(
            subjects=self.subjects,
            usage=UsageTotals(calls=1, input_tokens=10, output_tokens=2),
        )


class _FakeAnswer:
    """고정 답변을 돌려주는 fake 답변기다."""

    def __init__(self, text: str = "She works at Acme.") -> None:
        self.text = text
        self.calls: list[str] = []

    def __call__(
        self,
        *,
        question: str,
        question_date: datetime,
        claims_context: str,
    ) -> AnswerResult:
        self.calls.append(claims_context)
        return AnswerResult(
            answer=self.text,
            usage=UsageTotals(calls=1, input_tokens=30, output_tokens=5),
        )


def test_all_subjects_miss_abstains_without_calling_answer_llm() -> None:
    """subject가 전부 miss면 답변 LLM 없이 abstention을 쓴다."""
    extract = _FakeExtract(("Alice", "Bob"))
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=_lookup(),
        extract_subjects=extract,
        answer=answer,
    )

    assert outcome.hypothesis == ABSTENTION_ANSWER
    assert outcome.abstained is True
    assert answer.calls == []
    assert outcome.claims_context == ""
    assert all(trace.matched is False for trace in outcome.subjects)
    assert all(trace.matched_by is None for trace in outcome.subjects)


def test_matched_subject_with_no_claims_also_abstains() -> None:
    """대상은 찾았어도 claim이 없으면 재료가 없으므로 거절한다."""
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=_lookup(as_of={"Alice": _hit()}),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=answer,
    )

    assert outcome.hypothesis == ABSTENTION_ANSWER
    assert outcome.abstained is True
    assert answer.calls == []
    assert outcome.subjects[0].matched is True
    assert outcome.subjects[0].matched_by == "canonical_key"


def test_context_carries_valid_span_and_history_section() -> None:
    """컨텍스트에 valid 구간과 as-of·history 구분이 실린다."""
    live = _claim()
    closed = _claim(
        value="Globex",
        valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=_lookup(
            as_of={"Alice": _hit(live)},
            history={"Alice": _hit(live, closed)},
        ),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=answer,
    )

    context = outcome.claims_context
    assert "[employer] Acme" in context
    assert "2023-01-01T00:00:00+00:00~present" in context
    assert "2022-01-01T00:00:00+00:00~2023-01-01T00:00:00+00:00" in context
    assert "Alice works at Globex." in context
    assert "as of" in context.lower()
    assert "history" in context.lower()
    # live claim은 as-of 절에 이미 실렸으므로 history 절에서 반복하지
    # 않는다.
    assert context.count("[employer] Acme") == 1
    assert answer.calls == [context]
    assert outcome.hypothesis == "She works at Acme."
    assert outcome.abstained is False


def test_context_marks_unknown_valid_from() -> None:
    """언제부터인지 모르는 claim은 unknown으로 드러낸다."""
    context = render_claims_context(
        (
            (
                "Alice",
                _hit(_claim(valid_from=None)),
                _hit(),
            ),
        ),
        as_of=QUESTION_DATE,
    )

    assert "unknown~present" in context


def test_trace_records_every_subject_attempt() -> None:
    """trace가 subject별 시도와 claim 수를 빠짐없이 담는다."""
    outcome = run_question(
        _question("q7"),
        lookup=_lookup(
            as_of={"Alice": _hit(_claim())},
            history={"Alice": _hit(_claim(), _claim(value="Globex"))},
        ),
        extract_subjects=_FakeExtract(("Alice", "Bob")),
        answer=_FakeAnswer(),
    )

    payload = outcome.trace_payload()
    assert payload["question_id"] == "q7"
    assert payload["question_type"] == "knowledge-update"
    assert payload["abstained"] is False
    assert payload["subjects_tried"] == ["Alice", "Bob"]
    assert payload["as_of_claims"] == 1
    assert payload["history_claims"] == 2
    assert payload["elapsed_ms"] >= 0
    assert payload["usage"]["calls"] == 2
    assert payload["usage"]["input_tokens"] == 40
    assert payload["usage"]["output_tokens"] == 7
    assert payload["subjects"] == [
        {
            "subject": "Alice",
            "matched": True,
            "matched_by": "canonical_key",
            "display_name": "Alice",
            "as_of_claims": 1,
            "history_claims": 2,
        },
        {
            "subject": "Bob",
            "matched": False,
            "matched_by": None,
            "display_name": None,
            "as_of_claims": 0,
            "history_claims": 0,
        },
    ]


def test_subjects_are_capped_and_deduplicated() -> None:
    """subject 후보는 중복을 지우고 최대 개수까지만 조회한다."""
    seen: list[str] = []

    def _as_of(subject: str, at: datetime) -> AsOfQueryResult:
        seen.append(subject)
        return _miss()

    lookup = KnowledgeLookup(as_of=_as_of, history=lambda subject: _miss())
    extract = _FakeExtract(
        ("Alice", "Alice", "Bob", "Carol", "Dave", "Erin", "Frank")
    )

    outcome = run_question(
        _question(),
        lookup=lookup,
        extract_subjects=extract,
        answer=_FakeAnswer(),
    )

    assert seen == ["Alice", "Bob", "Carol", "Dave", "Erin"][:MAX_SUBJECTS]
    assert len(outcome.subjects) == MAX_SUBJECTS


def test_answer_prompt_orders_abstention_when_context_is_thin() -> None:
    """답변 프롬프트가 근거 없을 때의 거절 문구를 못박는다."""
    prompt = build_answer_prompt(
        question="Where does Alice work?",
        question_date=QUESTION_DATE,
        claims_context="- [employer] Acme (unknown~present)",
    )

    assert ABSTENTION_ANSWER in prompt
    assert "Where does Alice work?" in prompt
    assert "2023-06-01T00:00:00+00:00" in prompt
    assert "[employer] Acme" in prompt


def test_answer_questions_aggregates_usage_and_keeps_order() -> None:
    """여러 문항을 돌리면 순서를 지키고 사용량을 합산한다."""
    outcomes = answer_questions(
        [_question("q1"), _question("q2")],
        lookup=_lookup(as_of={"Alice": _hit(_claim())}),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=_FakeAnswer(),
    )

    assert [outcome.question_id for outcome in outcomes] == ["q1", "q2"]
    total = UsageTotals()
    for outcome in outcomes:
        total = total.plus(outcome.usage)
    assert total.calls == 4
    assert total.input_tokens == 80
    assert total.output_tokens == 14
