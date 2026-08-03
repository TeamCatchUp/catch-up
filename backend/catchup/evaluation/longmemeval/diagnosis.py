"""오답 문항 하나에 대표 실패 원인 하나를 붙인다.

점수만 있는 리포트는 "무엇을 고쳐야 하는가"에 답하지 못한다. 이
파이프라인은 수집 → 추출 → 해소 → 모순 판정 → 조회 → 답변으로 이어진
깔때기라서, 위쪽이 새면 아래쪽은 재료 없이 실패한다. 그래서 오답마다
증상을 다 적는 대신 가장 위에서 샌 곳 하나만 대표로 뽑는다.

상류 우선이 규칙의 전부다. subject를 못 찾은 문항은 컨텍스트도 비고
모순 결정도 없지만, 그 셋을 다 세면 진짜 원인 하나가 세 칸에 흩어져
분포가 고칠 곳을 가리키지 못한다.

이 모듈은 DB도 LLM도 부르지 않는다. QA trace 한 줄과 DB에서 미리 센
수치(`EvidenceStats`)만 받는다. 그 수치를 실제로 읽어 오는 일은
`grade.py`가 맡는다.

귀속은 근사다. 세 가지 한계를 안고 읽어야 한다.

1. 문항과 모순 안건은 claim 집합이 겹치는지로만 잇는다. 한 workspace에
   여러 문항의 세션이 섞이므로 다른 문항 때문에 열린 안건이 이 문항에
   잡힐 수 있다. 그래서 `conflict_missed`는 위음성 쪽으로 기운다 — 실제
   놓친 것보다 덜 잡힌다.
2. `extracted_claims`는 근거 세션 단위 집계이지 has_answer 턴 단위가
   아니다. 근거 세션의 다른 턴에서 나온 claim도 세므로
   `claim_not_extracted`는 실제보다 관대하다 — 실제 추출 실패보다 덜
   잡힌다.
3. QA trace는 승자 claim의 id를 담지 않는다. 그래서
   `adjudication_wrong`은 "판정 결과가 QA 컨텍스트에 안 실렸다"를
   컨텍스트 claim이 0인지로 근사한다. 승자가 아닌 다른 claim이 실려
   있으면 이 규칙은 걸리지 않고 `answer_generation`으로 흐른다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SUBJECT_MISS = "subject_miss"
"""조회 키가 어떤 노드에도 걸리지 않았음을 나타낸다."""

CLAIM_NOT_EXTRACTED = "claim_not_extracted"
"""정답 근거 세션에서 claim이 하나도 나오지 않았음을 나타낸다."""

CONFLICT_MISSED = "conflict_missed"
"""값이 바뀐 문항인데 모순 안건이 판정되지 않았음을 나타낸다."""

ADJUDICATION_WRONG = "adjudication_wrong"
"""모순은 판정됐는데 그 결과가 QA 컨텍스트까지 오지 않았음을 나타낸다.

trace에 승자 claim의 id가 없어서 "승자가 실렸는가"를 직접 못 본다.
컨텍스트 claim이 0인지로 근사한다.
"""

TEMPORAL_GAP = "temporal_gap"
"""시간 추론 문항에 과거 구간이 실리지 않았음을 나타낸다."""

ANSWER_GENERATION = "answer_generation"
"""재료가 다 있었는데 답변 문장이 틀렸음을 나타낸다."""

FAILURE_CAUSES: tuple[str, ...] = (
    SUBJECT_MISS,
    CLAIM_NOT_EXTRACTED,
    CONFLICT_MISSED,
    ADJUDICATION_WRONG,
    TEMPORAL_GAP,
    ANSWER_GENERATION,
)
"""귀속 우선순위 순서를 나타낸다. 리포트 표의 행 순서도 이것을 따른다."""

KNOWLEDGE_UPDATE_TYPE = "knowledge-update"
TEMPORAL_TYPE = "temporal-reasoning"


@dataclass(frozen=True, slots=True)
class EvidenceStats:
    """한 문항의 근거 세션에서 DB가 실제로 만든 것들을 센다.

    Attributes:
        extracted_claims: 정답 근거 세션에서 나온 claim candidate 수를
            나타낸다.
        contradictions_detected: 그 claim이 물린 모순 안건 수를
            나타낸다.
        contradictions_decided: 그중 결정(승인·적용·반려)이 내려진
            안건 수를 나타낸다.
    """

    extracted_claims: int = 0
    contradictions_detected: int = 0
    contradictions_decided: int = 0

    def as_dict(self) -> dict[str, int]:
        """grades 파일에 담을 형태로 바꾼다."""
        return {
            "extracted_claims": self.extracted_claims,
            "contradictions_detected": self.contradictions_detected,
            "contradictions_decided": self.contradictions_decided,
        }


@dataclass(frozen=True, slots=True)
class FailureAttribution:
    """대표 원인 하나와 그렇게 판정한 근거를 함께 담는다.

    Attributes:
        cause: `FAILURE_CAUSES` 중 하나를 나타낸다.
        evidence: 그 판정에 실제로 쓴 필드와 값을 담는다.
    """

    cause: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """grades 파일에 담을 형태로 바꾼다."""
        return {"cause": self.cause, "evidence": dict(self.evidence)}


def _subject_miss(trace_row: Mapping[str, Any]) -> bool:
    """subject 조회가 전부 빗나갔는지 읽는다.

    후보를 하나도 못 뽑은 경우도 miss다. QA 러너의 `all()`도 빈 목록을
    참으로 읽으므로 기본값을 같은 쪽으로 맞춘다 — 두 파일이 같은 실행을
    다르게 설명하면 안 된다.
    """
    subjects_tried = trace_row.get("subjects_tried") or ()
    return bool(trace_row.get("subject_miss", not subjects_tried))


def attribute_failure(
    trace_row: Mapping[str, Any],
    evidence_stats: EvidenceStats,
) -> FailureAttribution:
    """오답 문항 하나에 대표 실패 원인을 붙인다.

    위에서부터 처음 걸리는 규칙이 대표다. 증상이 겹쳐도 더 아래 규칙은
    보지 않는다.
    """
    question_type = str(trace_row.get("question_type") or "")
    subjects_tried = list(trace_row.get("subjects_tried") or ())
    as_of_claims = int(trace_row.get("as_of_claims") or 0)
    history_claims = int(trace_row.get("history_claims") or 0)
    context_claims = as_of_claims + history_claims

    if _subject_miss(trace_row):
        return FailureAttribution(
            cause=SUBJECT_MISS,
            evidence={
                "subject_miss": True,
                "subjects_tried": subjects_tried,
            },
        )

    if evidence_stats.extracted_claims == 0:
        return FailureAttribution(
            cause=CLAIM_NOT_EXTRACTED,
            evidence={
                "extracted_claims": 0,
                "subjects_tried": subjects_tried,
            },
        )

    if (
        question_type == KNOWLEDGE_UPDATE_TYPE
        and evidence_stats.contradictions_decided == 0
    ):
        return FailureAttribution(
            cause=CONFLICT_MISSED,
            evidence={
                "question_type": question_type,
                "contradictions_detected": (
                    evidence_stats.contradictions_detected
                ),
                "contradictions_decided": 0,
            },
        )

    if evidence_stats.contradictions_decided > 0 and context_claims == 0:
        return FailureAttribution(
            cause=ADJUDICATION_WRONG,
            evidence={
                "contradictions_decided": (
                    evidence_stats.contradictions_decided
                ),
                "context_claims": context_claims,
            },
        )

    if question_type == TEMPORAL_TYPE and history_claims == 0:
        return FailureAttribution(
            cause=TEMPORAL_GAP,
            evidence={
                "question_type": question_type,
                "history_claims": 0,
                "as_of_claims": as_of_claims,
            },
        )

    return FailureAttribution(
        cause=ANSWER_GENERATION,
        evidence={
            "context_claims": context_claims,
            "extracted_claims": evidence_stats.extracted_claims,
        },
    )
