"""QA 컨텍스트의 사건 타임라인 절이 세는 데 쓸 만한지 검증한다.

타임라인 절이 존재하는 이유는 "몇 번 갔었나"·"몇 번째인가"처럼 여러
세션에 흩어진 사건을 한 줄로 세워야 답이 나오는 질문이다. 그래서 이
파일이 지키는 선은 셋이다. 하나, 날짜 있는 사건에 날짜 순으로 번호가
붙는다 — 생성기는 번호를 읽기만 하면 된다. 둘, subject 절에 이미 실린
claim은 타임라인에 다시 싣지 않고, 전부 중복이면 절 자체를 내지
않는다. 셋, 타임라인 조회 경로가 없는 호출자는 예전과 똑같이 돈다.

DB도 LLM도 부르지 않는다. 조회와 모델 자리에 고정 응답 fake만 넣는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone

from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import run_question
from catchup.evaluation.longmemeval.usage import UsageTotals
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import MatchedSubject
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    TimelineQueryResult,
)

QUESTION_DATE = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _question() -> OracleQuestion:
    """평가 문항 하나를 만든다."""
    return OracleQuestion(
        question_id="q1",
        question_type="temporal-reasoning",
        question="How many times did Alice visit the clinic?",
        answer="twice",
        question_date=QUESTION_DATE,
        sessions=(),
        answer_session_ids=frozenset(),
    )


def _claim(
    predicate: str = "visited",
    value: str = "clinic",
    valid_from: datetime | None = None,
) -> AsOfClaim:
    """claim 한 건을 만든다."""
    return AsOfClaim(
        claim_id=uuid.uuid4(),
        predicate=predicate,
        value_type="text",
        value=value,
        statement=f"Alice visited the {value}.",
        valid_from=valid_from,
        valid_to=None,
    )


def _hit(*claims: AsOfClaim) -> AsOfQueryResult:
    """대상을 찾은 조회 결과를 만든다."""
    return AsOfQueryResult(
        subject=MatchedSubject(
            node_id=uuid.uuid4(),
            entity_type="person",
            display_name="Alice",
            matched_by="canonical_key",
        ),
        as_of=QUESTION_DATE,
        claims=tuple(claims),
    )


def _miss() -> AsOfQueryResult:
    """대상을 못 찾은 조회 결과를 만든다."""
    return AsOfQueryResult(subject=None, as_of=QUESTION_DATE, claims=())


def _lookup(
    *,
    as_of: AsOfQueryResult | None = None,
    history: AsOfQueryResult | None = None,
    timeline_claims: tuple[AsOfClaim, ...] | None = None,
) -> KnowledgeLookup:
    """고정 응답을 돌려주는 fake 조회를 만든다.

    `timeline_claims`가 None이면 타임라인 경로가 없는 예전 호출자다.
    """
    as_of_result = as_of or _miss()
    history_result = history or _miss()
    def timeline_fn(
        query_texts: Sequence[str], at: datetime
    ) -> TimelineQueryResult:
        """고정 타임라인 결과를 돌려준다."""
        return TimelineQueryResult(claims=timeline_claims or (), as_of=at)

    timeline = None if timeline_claims is None else timeline_fn
    return KnowledgeLookup(
        as_of=lambda subject, at: as_of_result,
        history=lambda subject: history_result,
        as_of_node=lambda node_id, at: _miss(),
        history_node=lambda node_id: _miss(),
        timeline=timeline,
    )


def _extract(question: str) -> SubjectResult:
    """고정 subject 후보를 돌려주는 fake 추출기다."""
    return SubjectResult(
        subjects=("clinic",),
        usage=UsageTotals(calls=1, input_tokens=10, output_tokens=2),
    )


def _answer(
    *,
    question: str,
    question_date: datetime,
    claims_context: str,
) -> AnswerResult:
    """고정 답변을 돌려주는 fake 답변기다."""
    return AnswerResult(
        answer="Twice.",
        usage=UsageTotals(calls=1, input_tokens=20, output_tokens=3),
    )


def test_timeline_section_renders_numbered_and_dated() -> None:
    """날짜 있는 사건에 날짜 순 번호가 붙고 미상은 뒤로 간다."""
    first = _claim(valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc))
    second = _claim(valid_from=datetime(2026, 7, 15, tzinfo=timezone.utc))
    undated = _claim(valid_from=None)

    outcome = run_question(
        _question(),
        lookup=_lookup(timeline_claims=(first, second, undated)),
        extract_subjects=_extract,
        answer=_answer,
    )

    context = outcome.claims_context
    assert "## Timeline" in context
    assert "1. 2026-07-01" in context
    assert "2. 2026-07-15" in context
    assert "(date unknown)" in context
    assert context.index("1. 2026-07-01") < context.index("2. 2026-07-15")
    assert context.index("2. 2026-07-15") < context.index("(date unknown)")
    assert outcome.timeline_used is True
    assert outcome.timeline_claims == 3
    trace = outcome.trace_payload()
    assert trace["timeline_used"] is True
    assert trace["timeline_claims"] == 3


def test_timeline_deduplicates_subject_claims() -> None:
    """subject 절에 이미 실린 claim은 타임라인에서 뺀다."""
    shared = _claim(valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc))
    fresh = _claim(valid_from=datetime(2026, 7, 15, tzinfo=timezone.utc))

    outcome = run_question(
        _question(),
        lookup=_lookup(
            as_of=_hit(shared),
            timeline_claims=(shared, fresh),
        ),
        extract_subjects=_extract,
        answer=_answer,
    )

    context = outcome.claims_context
    assert "## Timeline" in context
    timeline_text = context[context.index("## Timeline") :]
    assert str(shared.claim_id) not in timeline_text
    assert "1. 2026-07-15" in timeline_text
    assert "2026-07-01" not in timeline_text
    assert outcome.timeline_claims == 1


def test_timeline_section_absent_when_all_claims_duplicate() -> None:
    """실을 것이 남지 않으면 타임라인 절 자체를 내지 않는다."""
    shared = _claim(valid_from=datetime(2026, 7, 1, tzinfo=timezone.utc))

    outcome = run_question(
        _question(),
        lookup=_lookup(as_of=_hit(shared), timeline_claims=(shared,)),
        extract_subjects=_extract,
        answer=_answer,
    )

    assert "## Timeline" not in outcome.claims_context
    assert outcome.timeline_used is False
    assert outcome.timeline_claims == 0


def test_timeline_absent_when_lookup_missing() -> None:
    """타임라인 경로가 없는 호출자는 예전 동작 그대로 돈다."""
    outcome = run_question(
        _question(),
        lookup=_lookup(as_of=_hit(_claim())),
        extract_subjects=_extract,
        answer=_answer,
    )

    assert "## Timeline" not in outcome.claims_context
    assert outcome.timeline_used is False
    assert outcome.timeline_claims == 0
    assert outcome.trace_payload()["timeline_used"] is False
