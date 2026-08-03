"""오답의 대표 원인 귀속이 상류 우선 순위를 지키는지 검증한다.

깔때기 진단의 값어치는 "가장 위에서 새는 곳"을 하나만 지목하는 데
있다. 한 문항에 여러 증상이 겹칠 때 하류 증상을 대표로 뽑으면, 사실은
subject를 못 찾아 재료가 아예 없었던 문항이 "답변 생성 실패"로 집계돼
고칠 곳을 잘못 가리킨다. 그래서 겹침 케이스를 표로 못 박는다.

DB도 LLM도 부르지 않는다. trace 한 줄과 집계 수치만 넣는다.
"""

from __future__ import annotations

from typing import Any

from catchup.evaluation.longmemeval.diagnosis import ADJUDICATION_WRONG
from catchup.evaluation.longmemeval.diagnosis import ANSWER_GENERATION
from catchup.evaluation.longmemeval.diagnosis import CLAIM_NOT_EXTRACTED
from catchup.evaluation.longmemeval.diagnosis import CONFLICT_MISSED
from catchup.evaluation.longmemeval.diagnosis import FAILURE_CAUSES
from catchup.evaluation.longmemeval.diagnosis import SUBJECT_MISS
from catchup.evaluation.longmemeval.diagnosis import TEMPORAL_GAP
from catchup.evaluation.longmemeval.diagnosis import EvidenceStats
from catchup.evaluation.longmemeval.diagnosis import attribute_failure


def _trace(
    *,
    question_type: str = "multi-session",
    subject_miss: bool = False,
    as_of_claims: int = 3,
    history_claims: int = 2,
) -> dict[str, Any]:
    """QA 러너가 남기는 trace 한 줄을 흉내 낸다."""
    return {
        "question_id": "q1",
        "question_type": question_type,
        "abstained": False,
        "subjects_tried": ["Alice"],
        "subjects": [
            {
                "subject": "Alice",
                "matched": not subject_miss,
                "matched_by": None if subject_miss else "canonical_key",
                "display_name": None if subject_miss else "Alice",
                "as_of_claims": as_of_claims,
                "history_claims": history_claims,
            }
        ],
        "subject_miss": subject_miss,
        "as_of_claims": as_of_claims,
        "history_claims": history_claims,
        "future_claims_excluded": 0,
        "context_chars": 120,
        "elapsed_ms": 1200.0,
        "usage": {"calls": 2, "input_tokens": 10, "output_tokens": 5},
    }


def test_subject_miss_wins_over_every_downstream_symptom() -> None:
    """subject를 못 찾으면 하류 증상이 다 겹쳐도 subject_miss다."""
    result = attribute_failure(
        _trace(
            question_type="knowledge-update",
            subject_miss=True,
            as_of_claims=0,
            history_claims=0,
        ),
        EvidenceStats(
            extracted_claims=0,
            contradictions_detected=0,
            contradictions_decided=0,
        ),
    )

    assert result.cause == SUBJECT_MISS
    assert result.evidence["subject_miss"] is True
    assert result.evidence["subjects_tried"] == ["Alice"]


def test_claim_not_extracted_wins_over_conflict_missed() -> None:
    """근거 세션에서 claim이 안 나왔으면 모순 통계보다 그것이 먼저다."""
    result = attribute_failure(
        _trace(question_type="knowledge-update"),
        EvidenceStats(extracted_claims=0),
    )

    assert result.cause == CLAIM_NOT_EXTRACTED
    assert result.evidence["extracted_claims"] == 0


def test_conflict_missed_only_for_knowledge_update() -> None:
    """지식 갱신 문항인데 모순 결정이 0이면 감지 단계를 지목한다."""
    result = attribute_failure(
        _trace(question_type="knowledge-update"),
        EvidenceStats(extracted_claims=4, contradictions_decided=0),
    )

    assert result.cause == CONFLICT_MISSED
    assert result.evidence["contradictions_decided"] == 0


def test_conflict_missed_does_not_fire_for_other_types() -> None:
    """다른 유형은 모순 결정이 없어도 그것을 원인으로 삼지 않는다."""
    result = attribute_failure(
        _trace(question_type="multi-session"),
        EvidenceStats(extracted_claims=4, contradictions_decided=0),
    )

    assert result.cause == ANSWER_GENERATION


def test_adjudication_wrong_when_decision_and_context_both_exist() -> None:
    """모순을 판정했고 재료도 실렸는데 틀렸으면 판정을 의심한다."""
    result = attribute_failure(
        _trace(question_type="knowledge-update"),
        EvidenceStats(
            extracted_claims=4,
            contradictions_detected=2,
            contradictions_decided=2,
        ),
    )

    assert result.cause == ADJUDICATION_WRONG
    assert result.evidence["contradictions_decided"] == 2
    assert result.evidence["context_claims"] == 5


def test_adjudication_wrong_wins_over_temporal_gap() -> None:
    """구간이 비어도 모순 판정이 먼저 걸리면 그쪽이 대표다."""
    result = attribute_failure(
        _trace(question_type="temporal-reasoning", history_claims=0),
        EvidenceStats(
            extracted_claims=4,
            contradictions_detected=1,
            contradictions_decided=1,
        ),
    )

    assert result.cause == ADJUDICATION_WRONG


def test_temporal_gap_when_history_is_empty() -> None:
    """시간 추론 문항에 닫힌 구간이 하나도 안 실렸으면 구간 결손이다."""
    result = attribute_failure(
        _trace(question_type="temporal-reasoning", history_claims=0),
        EvidenceStats(extracted_claims=4),
    )

    assert result.cause == TEMPORAL_GAP
    assert result.evidence["history_claims"] == 0


def test_answer_generation_is_the_last_resort() -> None:
    """재료가 다 있었는데 틀리면 답변 생성 단계가 남는다."""
    result = attribute_failure(
        _trace(question_type="multi-session"),
        EvidenceStats(extracted_claims=7, contradictions_detected=0),
    )

    assert result.cause == ANSWER_GENERATION
    assert result.evidence["context_claims"] == 5


def test_missing_subject_trace_counts_as_subject_miss() -> None:
    """subject 후보를 하나도 못 뽑았으면 그것도 miss로 센다.

    후보가 비면 `all()`이 참이라 QA trace도 miss로 적는다. 진단이 그
    기본값을 다르게 읽으면 같은 실행을 두 파일이 다르게 설명한다.
    """
    result = attribute_failure(
        {"question_type": "multi-session"},
        EvidenceStats(extracted_claims=3),
    )

    assert result.cause == SUBJECT_MISS


def test_failure_causes_are_listed_in_priority_order() -> None:
    """리포트 표의 행 순서가 귀속 우선순위와 같은지 확인한다."""
    assert FAILURE_CAUSES == (
        SUBJECT_MISS,
        CLAIM_NOT_EXTRACTED,
        CONFLICT_MISSED,
        ADJUDICATION_WRONG,
        TEMPORAL_GAP,
        ANSWER_GENERATION,
    )
