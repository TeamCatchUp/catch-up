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
from catchup.evaluation.longmemeval.diagnosis import ANSWER_GENERATION
from catchup.evaluation.longmemeval.diagnosis import EvidenceStats
from catchup.evaluation.longmemeval.diagnosis import attribute_failure
from catchup.evaluation.longmemeval.qa_service import ABSTENTION_ANSWER
from catchup.evaluation.longmemeval.qa_service import MAX_SUBJECTS
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import SubjectLookup
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import answer_questions
from catchup.evaluation.longmemeval.qa_service import build_answer_prompt
from catchup.evaluation.longmemeval.qa_service import build_subject_prompt
from catchup.evaluation.longmemeval.qa_service import rank_similar_candidates
from catchup.evaluation.longmemeval.qa_service import render_claims_context
from catchup.evaluation.longmemeval.qa_service import run_question
from catchup.evaluation.longmemeval.usage import UsageTotals
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import MatchedSubject
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    SubjectCandidate,
)

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
    assert "### History (no longer true)" in context
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
            SubjectLookup(
                subject="Alice",
                as_of_result=_hit(_claim(valid_from=None)),
                history_result=_hit(),
            ),
        ),
        as_of=QUESTION_DATE,
    )

    assert "unknown~present" in context.text


def test_future_claim_is_excluded_and_counted_in_trace() -> None:
    """질문 시점 이후 발효 claim은 컨텍스트에서 빠지고 trace에 센다."""
    live = _claim()
    future = _claim(
        value="Initech",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
    )
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=_lookup(
            as_of={"Alice": _hit(live)},
            history={"Alice": _hit(live, future)},
        ),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=answer,
    )

    context = outcome.claims_context
    # 미래 사실이 "한때 참이었다"로 뒤집혀 실리면 temporal 답이 오염된다.
    assert "Initech" not in context
    assert "no longer true" not in context.lower()
    assert outcome.future_claims_excluded == 1
    assert outcome.trace_payload()["future_claims_excluded"] == 1


def test_future_only_history_leaves_subject_out_of_context() -> None:
    """미래 claim만 있는 대상은 절 자체가 만들어지지 않는다."""
    future = _claim(
        value="Initech",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    rendered = render_claims_context(
        (
            SubjectLookup(
                subject="Alice",
                as_of_result=_hit(),
                history_result=_hit(future),
            ),
        ),
        as_of=QUESTION_DATE,
    )

    assert rendered.text == ""
    assert rendered.future_claims_excluded == 1


def test_closed_past_claim_stays_in_no_longer_true_section() -> None:
    """질문 시점에 이미 끝난 claim은 no longer true 절에 남는다."""
    closed = _claim(
        value="Globex",
        valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
        valid_to=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )

    rendered = render_claims_context(
        (
            SubjectLookup(
                subject="Alice",
                as_of_result=_hit(_claim()),
                history_result=_hit(closed),
            ),
        ),
        as_of=QUESTION_DATE,
    )

    assert "### History (no longer true)" in rendered.text
    assert "[employer] Globex" in rendered.text
    assert "validity unknown" not in rendered.text
    assert rendered.future_claims_excluded == 0


def test_unbounded_history_claim_goes_to_validity_unknown() -> None:
    """구간이 불명한 claim은 끝났다고 단정하지 않고 따로 싣는다."""
    unclear = _claim(value="Globex", valid_from=None, valid_to=None)

    rendered = render_claims_context(
        (
            SubjectLookup(
                subject="Alice",
                as_of_result=_hit(_claim()),
                history_result=_hit(unclear),
            ),
        ),
        as_of=QUESTION_DATE,
    )

    assert "### History (validity unknown)" in rendered.text
    assert "no longer true" not in rendered.text.lower()
    assert "[employer] Globex (unknown~present)" in rendered.text


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
    assert payload["future_claims_excluded"] == 0
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


def _candidate(
    display_name: str | None = "Alice Kim",
    score: float = 0.42,
) -> SubjectCandidate:
    """정확 매칭이 빗나갔을 때 함께 오는 유사 후보 하나를 만든다."""
    return SubjectCandidate(
        node_id=uuid.uuid4(),
        display_name=display_name,
        entity_type="person",
        score=score,
    )


def _miss_with(*candidates: SubjectCandidate) -> AsOfQueryResult:
    """유사 후보를 달고 온 miss 결과를 만든다."""
    return AsOfQueryResult(
        subject=None,
        as_of=QUESTION_DATE,
        claims=(),
        similar_candidates=tuple(candidates),
    )


class _RecordingLookup:
    """조회 호출을 순서대로 기록하는 fake 조회다."""

    def __init__(
        self,
        as_of: dict[str, AsOfQueryResult] | None = None,
        history: dict[str, AsOfQueryResult] | None = None,
    ) -> None:
        self.as_of_map = as_of or {}
        self.history_map = history or {}
        self.calls: list[str] = []

    def as_lookup(self) -> KnowledgeLookup:
        """qa_service가 받는 조회 묶음으로 감싼다."""
        return KnowledgeLookup(as_of=self._as_of, history=self._history)

    def _as_of(self, subject: str, at: datetime) -> AsOfQueryResult:
        self.calls.append(subject)
        return self.as_of_map.get(subject, _miss())

    def _history(self, subject: str) -> AsOfQueryResult:
        return self.history_map.get(subject, _miss())


def test_similar_candidate_is_requeried_and_loaded_with_label() -> None:
    """miss에 후보가 있으면 그 이름으로 다시 조회해 라벨로 싣는다."""
    lookup = _RecordingLookup(
        as_of={"Alice": _miss_with(_candidate())},
        history={
            "Alice": _miss_with(_candidate()),
            "Alice Kim": _hit(_claim()),
        },
    )
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=answer,
        use_similarity_fallback=True,
    )

    assert lookup.calls == ["Alice", "Alice Kim"]
    context = outcome.claims_context
    assert "(similar match: Alice Kim, score 0.42)" in context
    assert "[employer] Acme" in context
    assert answer.calls == [context]
    assert outcome.abstained is False

    payload = outcome.trace_payload()
    assert payload["similarity_used"] is True
    assert payload["similarity_candidates"] == [
        {
            "name": "Alice Kim",
            "score": 0.42,
            "claims_found": 1,
            "skipped": False,
        }
    ]


def test_fallback_claims_are_counted_apart_from_exact_match() -> None:
    """되짚기가 실은 재료는 정확 매칭 수치와 따로 세어 trace에 남는다.

    정확 매칭이 다 빗나간 문항은 `as_of_claims`가 0이다. 되짚은 몫까지
    그 0에 묻히면 진단 하류 규칙이 "컨텍스트가 비었다"로 읽는다.
    """
    lookup = _RecordingLookup(
        as_of={
            "Alice": _miss_with(_candidate()),
            "Alice Kim": _hit(_claim()),
        },
        history={
            "Alice Kim": _hit(
                _claim(
                    value="Globex",
                    valid_to=datetime(2023, 3, 1, tzinfo=timezone.utc),
                )
            ),
        },
    )

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=_FakeAnswer(),
    )

    payload = outcome.trace_payload()
    assert payload["subject_miss"] is True
    assert payload["as_of_claims"] == 0
    assert payload["history_claims"] == 0
    assert payload["fallback_as_of_claims"] == 1
    assert payload["fallback_history_claims"] == 1
    assert payload["similarity_used"] is True


def test_runner_fallback_trace_reaches_answer_generation() -> None:
    """러너가 실제로 만든 fallback trace는 답변 생성 단계로 흐른다.

    러너가 못 만드는 모양(subject_miss + 정확 매칭 claim > 0)으로 진단을
    검증하면, 하류 규칙이 fallback 수치를 무시해도 테스트가 통과해 버린다.
    그래서 여기서는 러너 출력을 그대로 진단에 넣는다.
    """
    lookup = _RecordingLookup(
        as_of={
            "Alice": _miss_with(_candidate()),
            "Alice Kim": _hit(_claim()),
        },
    )

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=_FakeAnswer(),
    )

    attribution = attribute_failure(
        outcome.trace_payload(),
        EvidenceStats(
            extracted_claims=4,
            contradictions_detected=2,
            contradictions_decided=2,
        ),
    )

    assert attribution.cause == ANSWER_GENERATION
    assert attribution.evidence["context_claims"] == 1


def test_similar_candidates_break_score_ties_by_node_id() -> None:
    """점수가 같으면 node_id로 갈라 순서를 고정한다."""
    first = SubjectCandidate(
        node_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        display_name="Alice Kim",
        entity_type="person",
        score=0.42,
    )
    second = SubjectCandidate(
        node_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        display_name="Alice Lee",
        entity_type="person",
        score=0.42,
    )

    ranked = rank_similar_candidates(
        _miss_with(second, first),
        _miss_with(first, second),
    )

    assert [item.node_id for item in ranked] == [
        first.node_id,
        second.node_id,
    ]


def test_similarity_fallback_off_keeps_the_old_abstention_path() -> None:
    """off면 후보가 있어도 재조회하지 않고 기존 abstention으로 닫는다."""
    lookup = _RecordingLookup(
        as_of={"Alice": _miss_with(_candidate())},
        history={"Alice Kim": _hit(_claim())},
    )
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=answer,
        use_similarity_fallback=False,
    )

    assert lookup.calls == ["Alice"]
    assert outcome.claims_context == ""
    assert outcome.hypothesis == ABSTENTION_ANSWER
    assert outcome.abstained is True
    assert answer.calls == []

    payload = outcome.trace_payload()
    assert payload["similarity_used"] is False
    assert payload["similarity_candidates"] == []


def test_all_candidates_empty_still_abstains() -> None:
    """후보를 다 되짚어도 claim이 없으면 그대로 거절한다."""
    lookup = _RecordingLookup(
        as_of={"Alice": _miss_with(_candidate(), _candidate("Alicia", 0.2))},
    )
    answer = _FakeAnswer()

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=answer,
    )

    assert lookup.calls == ["Alice", "Alice Kim", "Alicia"]
    assert outcome.claims_context == ""
    assert outcome.hypothesis == ABSTENTION_ANSWER
    assert outcome.abstained is True
    assert answer.calls == []

    payload = outcome.trace_payload()
    assert payload["similarity_used"] is False
    assert [item["name"] for item in payload["similarity_candidates"]] == [
        "Alice Kim",
        "Alicia",
    ]
    assert all(
        item["claims_found"] == 0
        for item in payload["similarity_candidates"]
    )


def test_candidate_without_display_name_is_skipped_and_traced() -> None:
    """이름 없는 후보는 재조회할 수 없으므로 건너뛰고 trace에 남긴다."""
    lookup = _RecordingLookup(
        as_of={"Alice": _miss_with(_candidate(None, 0.5), _candidate())},
        history={"Alice Kim": _hit(_claim())},
    )

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=_FakeAnswer(),
    )

    assert lookup.calls == ["Alice", "Alice Kim"]
    payload = outcome.trace_payload()
    assert payload["similarity_candidates"] == [
        {"name": None, "score": 0.5, "claims_found": 0, "skipped": True},
        {
            "name": "Alice Kim",
            "score": 0.42,
            "claims_found": 1,
            "skipped": False,
        },
    ]
    assert payload["similarity_used"] is True


def test_candidate_requery_does_not_chain_into_another_hop() -> None:
    """재조회가 또 후보를 물고 와도 한 단계에서 멈춘다."""
    lookup = _RecordingLookup(
        as_of={
            "Alice": _miss_with(_candidate()),
            "Alice Kim": _miss_with(_candidate("Alicia Kim", 0.3)),
        },
    )

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=_FakeAnswer(),
    )

    assert lookup.calls == ["Alice", "Alice Kim"]
    assert outcome.abstained is True


def test_matched_subject_does_not_trigger_similarity_fallback() -> None:
    """정확 매칭이 걸린 subject는 후보 경로를 아예 타지 않는다."""
    lookup = _RecordingLookup(
        as_of={"Alice": _hit(_claim())},
    )

    outcome = run_question(
        _question(),
        lookup=lookup.as_lookup(),
        extract_subjects=_FakeExtract(("Alice",)),
        answer=_FakeAnswer(),
    )

    assert lookup.calls == ["Alice"]
    assert outcome.trace_payload()["similarity_candidates"] == []
    assert outcome.trace_payload()["similarity_used"] is False


def test_subject_prompt_allows_generic_noun_phrases() -> None:
    """subject 프롬프트가 제네릭 명사구까지 뽑게 지시한다.

    지식 베이스의 canonical entity 이름에는 "desktop computer" 같은
    제네릭 명사구가 많다. 고유명사만 요구하면 추출이 빈 목록을 내고
    문항 전체가 abstention으로 떨어지므로, 지시 문구를 고정한다.
    """
    prompt = build_subject_prompt("What did I buy for my desktop computer?")

    assert "named or generic noun phrases" in prompt
    assert "desktop computer" in prompt
    assert "Return an empty list only when the question is about no" in prompt
    assert "bare greeting" in prompt
    assert '"my car" becomes "car"' in prompt
    assert f"List at most {MAX_SUBJECTS} subjects" in prompt
    assert "Do not translate,\n  expand, or invent names." in prompt
    assert "Use noun phrases only." in prompt
    assert prompt.endswith("What did I buy for my desktop computer?\n")
