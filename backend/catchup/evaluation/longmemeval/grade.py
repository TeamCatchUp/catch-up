"""LongMemEval 답변을 채점하고 깔때기 진단 리포트를 쓴다.

채점은 문자열 일치가 아니라 LLM 판정이다. 같은 사실을 다른 문장으로
쓰면 정답이어야 하는데, 문자열 비교는 그것을 오답으로 센다.

판정 프롬프트는 공식 `evaluate_qa.py`의 재현이 아니라 이식이다.
오프라인이라 원문을 대조하지 못했고, 스펙에 적힌 유형별 규칙(시간
추론의 ±1 허용, 지식 갱신의 최신 값 요구, abstention의 "모른다가
정답")을 그대로 옮겨 썼다. 그래서 이 값은 공식 리더보드 점수와 직접
비교할 수 없다. 리포트가 그 사실을 매번 적는다.

읽지 못한 판정은 오답으로 세지 않고 error로 따로 센다. 못 읽은 응답을
조용히 오답으로 접으면 점수가 낮아진 이유가 파이프라인인지 채점기인지
구분되지 않는다.

리포트의 값어치는 점수가 아니라 귀속이다. 오답마다 깔때기 어디에서
샜는지를 하나로 지목하려면 QA trace만으로는 모자라서, 근거 세션에서
claim이 실제로 나왔는지와 모순 안건이 판정됐는지를 DB에서 읽는다.
읽기 전용이며 `knowledge_maintenance`를 거치지 않고 evaluation 쪽에서
직접 select한다 — 진단용 조회는 지식 유지보수의 계약이 아니다.

실행:
    uv run python -m catchup.evaluation.longmemeval.grade \\
        --workspace-id 902 \\
        --results-dir experiments/longmemeval/results/
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from collections import Counter
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from sqlalchemy import String
from sqlalchemy import cast
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.db.models import KnowledgeCandidateEvidenceLink
from catchup.db.models import KnowledgeClaimCandidate
from catchup.db.models import KnowledgeMutationOperation
from catchup.db.models import KnowledgeMutationProposal
from catchup.db.models import KnowledgeNode
from catchup.db.models import Observation
from catchup.db.models import SourceVersion
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.dataset import load_oracle
from catchup.evaluation.longmemeval.dataset import select_subset
from catchup.evaluation.longmemeval.diagnosis import FAILURE_CAUSES
from catchup.evaluation.longmemeval.diagnosis import EvidenceStats
from catchup.evaluation.longmemeval.diagnosis import FailureAttribution
from catchup.evaluation.longmemeval.diagnosis import attribute_failure
from catchup.evaluation.longmemeval.draft_vocabulary import UsageTotals
from catchup.evaluation.longmemeval.draft_vocabulary import usage_from_message
from catchup.evaluation.longmemeval.run_qa import DEFAULT_ORACLE_PATH
from catchup.evaluation.longmemeval.run_qa import RESULTS_FILENAME
from catchup.evaluation.longmemeval.run_qa import TRACE_FILENAME
from catchup.evaluation.longmemeval.run_qa import USAGE_FILENAME

DEFAULT_WORKSPACE_ID = 902
GRADES_FILENAME = "grades.jsonl"
REPORT_FILENAME = "report.md"
GRADE_USAGE_FILENAME = "grade_usage.json"

DEFAULT_INPUT_PRICE = 3.0
DEFAULT_OUTPUT_PRICE = 15.0
TOKENS_PER_UNIT_PRICE = 1_000_000

VERDICT_YES = "yes"
VERDICT_NO = "no"
VERDICT_ERROR = "error"

JUDGE_PROMPT_VERSION = "catchup-port-of-longmemeval-evaluate_qa/v1"
"""채점 프롬프트의 출처와 판을 나타낸다.

공식 저장소의 `evaluate_qa.py` 원문을 그대로 옮긴 것이 아니라, 그
프롬프트가 유형별로 나뉜다는 사실과 각 유형의 판정 규칙만 이식한
것이다. 점수를 공식 리더보드와 나란히 놓을 수 없다는 뜻이므로 버전
문자열을 리포트에 남긴다.
"""

# 모순 안건에 사람(여기서는 벤치마크 규칙)이 결정을 내린 상태다.
# pending은 아직 아무도 판단하지 않은 것이라 결정으로 세지 않는다.
DECIDED_PROPOSAL_STATUSES = frozenset({"approved", "applied", "rejected"})
CONTRADICTION_KIND = "contradiction"

DEFAULT_RULE = (
    "The response is correct if it conveys the same information as the "
    "reference answer, even when it is worded differently or adds "
    "harmless detail. Answer no if it omits, contradicts, or changes the "
    "fact the reference answer states."
)

TEMPORAL_RULE = (
    "This question asks about dates, durations, or ordering. The response "
    "is correct if its calculation matches the reference answer within one "
    "unit of whatever the question asks about (one day, one week, one "
    "month, or one year). Answer no if the gap is larger than one unit or "
    "the direction in time is wrong."
)

KNOWLEDGE_UPDATE_RULE = (
    "The reference answer states the most recent value, after the fact "
    "changed. The response is correct only if it gives that latest value. "
    "Answer no if it gives only an older, superseded value, even when that "
    "older value was once true."
)

ABSTENTION_RULE = (
    "The information needed to answer this question was never present in "
    "the conversation history, so there is no reference answer. The "
    "response is correct only if it says it does not know or has no "
    "information about it. Answer no if it states any specific fact as the "
    "answer, however plausible it sounds."
)

JUDGE_PROMPT_TEMPLATE = """\
You are grading one answer produced by a long-term memory QA system.

Grading rule:
{rule}

Question:
{question}

{reference_block}
Response to grade:
{hypothesis}

Reply with exactly one word, "yes" or "no". No punctuation, no
explanation.
Answer:"""

REFERENCE_BLOCK_TEMPLATE = """\
Reference answer:
{answer}
"""

ABSTENTION_REFERENCE_BLOCK = """\
Reference answer:
(none — the conversation history never contained this information)
"""


def judge_rule(question_type: str, *, is_abstention: bool) -> str:
    """이 문항을 어느 규칙으로 잴지 고른다.

    abstention이 유형보다 먼저다. `_abs` 문항에는 정답 정보 자체가
    haystack에 없어서 유형별 규칙으로 재면 "모른다"가 전부 오답이 된다.
    """
    if is_abstention:
        return ABSTENTION_RULE
    if question_type == "temporal-reasoning":
        return TEMPORAL_RULE
    if question_type == "knowledge-update":
        return KNOWLEDGE_UPDATE_RULE
    return DEFAULT_RULE


def build_judge_prompt(
    *,
    question: str,
    answer: str,
    hypothesis: str,
    question_type: str,
    is_abstention: bool,
) -> str:
    """판정 프롬프트 한 건을 만든다.

    abstention 문항에는 정답을 싣지 않는다. 없는 정답을 지어내 보여주면
    채점자가 "정답과 같은가"를 재게 되어, 재려던 것("모른다고 말했는가")
    이 아닌 값이 나온다.
    """
    if is_abstention:
        reference_block = ABSTENTION_REFERENCE_BLOCK
    else:
        reference_block = REFERENCE_BLOCK_TEMPLATE.format(answer=answer)
    return JUDGE_PROMPT_TEMPLATE.format(
        rule=judge_rule(question_type, is_abstention=is_abstention),
        question=question.strip(),
        reference_block=reference_block,
        hypothesis=hypothesis.strip(),
    )


def parse_verdict(text: str | None) -> str:
    """판정 응답의 첫 단어만 읽어 yes·no·error로 접는다.

    읽지 못한 응답을 오답으로 세지 않는다. 그러면 점수가 낮아진 이유가
    파이프라인인지 채점기인지 사후에 구분되지 않는다.
    """
    words = (text or "").strip().split()
    if not words:
        return VERDICT_ERROR
    token = words[0].strip("*_`\"'.,!:;()[]").casefold()
    if token == VERDICT_YES:
        return VERDICT_YES
    if token == VERDICT_NO:
        return VERDICT_NO
    return VERDICT_ERROR


def estimate_cost(
    usage: UsageTotals,
    *,
    input_price: float,
    output_price: float,
) -> float:
    """토큰 사용량을 백만 토큰 단가로 환산한다."""
    return (
        usage.input_tokens / TOKENS_PER_UNIT_PRICE * input_price
        + usage.output_tokens / TOKENS_PER_UNIT_PRICE * output_price
    )


@dataclass(frozen=True, slots=True)
class JudgeResult:
    """판정 호출 한 번의 결과를 담는다.

    Attributes:
        verdict: yes·no·error 중 하나를 나타낸다.
        raw: 모델이 실제로 쓴 응답을 그대로 담는다.
        usage: 판정 호출이 쓴 토큰을 담는다.
    """

    verdict: str
    raw: str
    usage: UsageTotals = field(default_factory=UsageTotals)


JudgeFn = Callable[..., JudgeResult]
"""문항 하나를 판정하는 함수를 나타낸다."""


@dataclass(frozen=True, slots=True)
class GradeRow:
    """문항 한 건의 채점 결과와 진단 근거를 담는다.

    Attributes:
        question_id: 문항 식별자를 나타낸다.
        question_type: 유형별 집계에 쓸 질문 유형을 나타낸다.
        is_abstention: 거절이 정답인 문항인지 나타낸다.
        verdict: yes·no·error 중 하나를 나타낸다.
        hypothesis: 채점 대상 답변을 담는다.
        judge_raw: 판정 모델의 원문 응답을 담는다.
        abstained: QA 러너가 답변을 거절했는지 나타낸다.
        subject_miss: subject 조회가 전부 빗나갔는지 나타낸다.
        evidence_stats: 근거 세션에서 DB가 만든 것들의 집계를 담는다.
        attribution: 오답일 때의 대표 원인을 담고, 그 밖에는 None이다.
        usage: 이 문항 판정이 쓴 토큰을 담는다.
    """

    question_id: str
    question_type: str
    is_abstention: bool
    verdict: str
    hypothesis: str
    judge_raw: str
    abstained: bool
    subject_miss: bool
    evidence_stats: EvidenceStats
    attribution: FailureAttribution | None
    usage: UsageTotals

    @property
    def bucket(self) -> str:
        """유형별 표에서 이 문항이 들어갈 행 이름을 나타낸다."""
        if self.is_abstention:
            return f"{self.question_type} (abstention)"
        return self.question_type

    def as_dict(self) -> dict[str, Any]:
        """grades 파일에 담을 한 줄로 바꾼다."""
        return {
            "question_id": self.question_id,
            "question_type": self.question_type,
            "is_abstention": self.is_abstention,
            "verdict": self.verdict,
            "hypothesis": self.hypothesis,
            "judge_raw": self.judge_raw,
            "abstained": self.abstained,
            "subject_miss": self.subject_miss,
            "evidence_stats": self.evidence_stats.as_dict(),
            "attribution": (
                None
                if self.attribution is None
                else self.attribution.as_dict()
            ),
            "usage": self.usage.as_dict(),
        }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSONL 파일을 한 줄씩 읽어 dict 목록으로 돌려준다."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def grade_questions(
    results: Sequence[Mapping[str, Any]],
    *,
    questions: Mapping[str, OracleQuestion],
    traces: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, EvidenceStats],
    judge: JudgeFn,
    on_row: Callable[[GradeRow], None] | None = None,
) -> list[GradeRow]:
    """답변 목록을 하나씩 판정하고 오답에 원인을 붙인다.

    귀속은 오답(`no`)에만 붙인다. 못 읽은 판정(`error`)에 원인을 붙이면
    파이프라인이 실패했다는 증거가 없는데도 실패 분포가 커진다.
    """
    rows: list[GradeRow] = []
    for result in results:
        question_id = str(result["question_id"])
        question = questions.get(question_id)
        if question is None:
            continue
        hypothesis = str(result.get("hypothesis") or "")
        trace = traces.get(question_id, {})
        stats = evidence.get(question_id, EvidenceStats())

        judged = judge(
            question=question.question,
            answer=question.answer,
            hypothesis=hypothesis,
            question_type=question.question_type,
            is_abstention=question.is_abstention,
        )
        attribution = (
            attribute_failure(trace, stats)
            if judged.verdict == VERDICT_NO
            else None
        )
        row = GradeRow(
            question_id=question_id,
            question_type=question.question_type,
            is_abstention=question.is_abstention,
            verdict=judged.verdict,
            hypothesis=hypothesis,
            judge_raw=judged.raw,
            abstained=bool(trace.get("abstained", False)),
            subject_miss=bool(
                trace.get("subject_miss", not trace.get("subjects_tried"))
            ),
            evidence_stats=stats,
            attribution=attribution,
            usage=judged.usage,
        )
        rows.append(row)
        if on_row is not None:
            on_row(row)
    return rows


def load_claim_sessions(
    session: Session,
    *,
    workspace_id: int,
) -> dict[uuid.UUID, set[str]]:
    """claim candidate마다 그 근거가 온 세션 식별자를 모은다.

    사슬은 claim candidate → evidence link → observation node →
    observation → source version이다. 수집 러너가 세션 하나를 문서
    하나로 넣으면서 `external_document_id`에 session_id를 그대로 썼으므로
    마지막 칸이 곧 세션 식별자다.

    `resource_id`는 문자열 칸이라 UUID를 캐스팅해 잇는다.
    """
    rows = session.execute(
        select(
            KnowledgeCandidateEvidenceLink.claim_candidate_id,
            SourceVersion.external_document_id,
        )
        .join(
            KnowledgeNode,
            (
                KnowledgeNode.id
                == KnowledgeCandidateEvidenceLink.evidence_node_id
            )
            & (
                KnowledgeNode.workspace_id
                == KnowledgeCandidateEvidenceLink.workspace_id
            ),
        )
        .join(
            Observation,
            (cast(Observation.id, String) == KnowledgeNode.resource_id)
            & (Observation.workspace_id == KnowledgeNode.workspace_id),
        )
        .join(
            SourceVersion,
            (SourceVersion.id == Observation.source_version_id)
            & (SourceVersion.workspace_id == Observation.workspace_id),
        )
        .where(
            KnowledgeCandidateEvidenceLink.workspace_id == workspace_id,
            KnowledgeCandidateEvidenceLink.claim_candidate_id.isnot(None),
            KnowledgeNode.resource_type == "observation",
        )
    ).all()

    mapping: dict[uuid.UUID, set[str]] = {}
    for claim_candidate_id, external_document_id in rows:
        mapping.setdefault(claim_candidate_id, set()).add(
            external_document_id
        )
    return mapping


@dataclass(frozen=True, slots=True)
class ContradictionProposal:
    """모순 안건 하나와 거기 물린 claim candidate를 담는다.

    Attributes:
        proposal_id: 안건 식별자를 나타낸다.
        status: 안건의 현재 상태를 나타낸다.
        claim_candidate_ids: 이 안건이 건드리는 claim 후보를 담는다.
    """

    proposal_id: uuid.UUID
    status: str
    claim_candidate_ids: frozenset[uuid.UUID]

    @property
    def decided(self) -> bool:
        """규칙이 승패를 정한 안건인지 나타낸다."""
        return self.status in DECIDED_PROPOSAL_STATUSES


def load_contradiction_proposals(
    session: Session,
    *,
    workspace_id: int,
) -> list[ContradictionProposal]:
    """모순 안건과 그 안건이 건드리는 claim 후보를 읽는다.

    trigger 하나만 보면 안 된다. 안건의 trigger는 모순 그룹의 한 쪽일
    뿐이라, 정답 근거가 진 쪽에 있으면 문항과 안건이 이어지지 않는다.
    그래서 operation이 가리키는 claim 후보까지 합쳐 본다.
    """
    proposals = session.execute(
        select(
            KnowledgeMutationProposal.id,
            KnowledgeMutationProposal.status,
            KnowledgeMutationProposal.trigger_claim_candidate_id,
        ).where(
            KnowledgeMutationProposal.workspace_id == workspace_id,
            KnowledgeMutationProposal.proposal_kind == CONTRADICTION_KIND,
        )
    ).all()
    if not proposals:
        return []

    proposal_ids = [row[0] for row in proposals]
    operations = session.execute(
        select(
            KnowledgeMutationOperation.proposal_id,
            KnowledgeMutationOperation.claim_candidate_id,
        ).where(
            KnowledgeMutationOperation.workspace_id == workspace_id,
            KnowledgeMutationOperation.proposal_id.in_(proposal_ids),
            KnowledgeMutationOperation.claim_candidate_id.isnot(None),
        )
    ).all()

    by_proposal: dict[uuid.UUID, set[uuid.UUID]] = {}
    for proposal_id, claim_candidate_id in operations:
        by_proposal.setdefault(proposal_id, set()).add(claim_candidate_id)

    collected: list[ContradictionProposal] = []
    for proposal_id, status, trigger_claim_id in proposals:
        claim_ids = set(by_proposal.get(proposal_id, ()))
        if trigger_claim_id is not None:
            claim_ids.add(trigger_claim_id)
        collected.append(
            ContradictionProposal(
                proposal_id=proposal_id,
                status=status,
                claim_candidate_ids=frozenset(claim_ids),
            )
        )
    return collected


def build_evidence_stats(
    questions: Iterable[OracleQuestion],
    *,
    claim_sessions: Mapping[uuid.UUID, set[str]],
    proposals: Sequence[ContradictionProposal],
) -> dict[str, EvidenceStats]:
    """문항마다 근거 세션이 실제로 만든 것들을 센다.

    기준은 oracle이 지목한 `answer_session_ids`다. 그 세션에서 나온
    claim이 0이면 조회가 아니라 추출에서 샌 것이고, 그 claim이 물린
    모순 안건이 0이면 감지에서 샌 것이다.
    """
    stats: dict[str, EvidenceStats] = {}
    for question in questions:
        session_ids = set(question.answer_session_ids)
        claim_ids = {
            claim_id
            for claim_id, sessions in claim_sessions.items()
            if sessions & session_ids
        }
        detected = [
            proposal
            for proposal in proposals
            if proposal.claim_candidate_ids & claim_ids
        ]
        stats[question.question_id] = EvidenceStats(
            extracted_claims=len(claim_ids),
            contradictions_detected=len(detected),
            contradictions_decided=sum(
                1 for proposal in detected if proposal.decided
            ),
        )
    return stats


def load_vocabulary_snapshots(
    session: Session,
    *,
    workspace_id: int,
) -> list[tuple[str, str, int]]:
    """추출에 실제로 쓰인 어휘 스냅샷과 그 건수를 읽는다.

    스냅샷이 하나가 아니면 같은 workspace 안에서 서로 다른 규칙으로 뽑힌
    claim이 섞였다는 뜻이라 점수를 하나의 어휘 아래 해석할 수 없다. 그
    사실을 사후 검토 플래그로 리포트에 남긴다.
    """
    rows = session.execute(
        select(
            KnowledgeClaimCandidate.ontology_id,
            KnowledgeClaimCandidate.ontology_version,
            func.count().label("candidates"),
        )
        .where(KnowledgeClaimCandidate.workspace_id == workspace_id)
        .group_by(
            KnowledgeClaimCandidate.ontology_id,
            KnowledgeClaimCandidate.ontology_version,
        )
        .order_by(
            KnowledgeClaimCandidate.ontology_id,
            KnowledgeClaimCandidate.ontology_version,
        )
    ).all()
    return [(row[0], row[1], int(row[2])) for row in rows]


@dataclass(frozen=True, slots=True)
class ReportInputs:
    """리포트 한 장을 쓰는 데 필요한 모든 값을 담는다.

    Attributes:
        workspace_id: 지식을 읽어 온 평가 workspace를 나타낸다.
        results_dir: 채점한 결과 디렉토리를 나타낸다.
        rows: 문항별 채점 결과를 담는다.
        qa_usage: QA 러너가 쓴 토큰 집계를 담는다.
        qa_elapsed_ms: QA trace의 문항 소요 시간 합을 담는다.
        grade_elapsed_ms: 이번 채점 실행의 실측 소요 시간을 담는다.
        contradiction_total: workspace 전체 모순 안건 수를 나타낸다.
        contradiction_decided: 그중 결정이 내려진 안건 수를 나타낸다.
        vocabulary_snapshots: 추출에 쓰인 어휘 스냅샷 목록을 담는다.
        input_price: 입력 토큰 백만 개당 단가를 나타낸다.
        output_price: 출력 토큰 백만 개당 단가를 나타낸다.
    """

    workspace_id: int
    results_dir: Path
    rows: tuple[GradeRow, ...]
    qa_usage: UsageTotals
    qa_elapsed_ms: float
    grade_elapsed_ms: float
    contradiction_total: int
    contradiction_decided: int
    vocabulary_snapshots: tuple[tuple[str, str, int], ...]
    input_price: float = DEFAULT_INPUT_PRICE
    output_price: float = DEFAULT_OUTPUT_PRICE

    @property
    def judge_usage(self) -> UsageTotals:
        """채점이 쓴 토큰 합계를 나타낸다."""
        total = UsageTotals()
        for row in self.rows:
            total = total.plus(row.usage)
        return total


def _ratio(part: int, whole: int) -> str:
    """비율을 백분율 문자열로 만든다. 분모가 0이면 대시를 쓴다."""
    if whole <= 0:
        return "-"
    return f"{part / whole * 100:.1f}%"


def render_report(inputs: ReportInputs) -> str:
    """채점 결과를 리포트 markdown 한 장으로 편다."""
    rows = inputs.rows
    graded = [row for row in rows if row.verdict != VERDICT_ERROR]
    correct = [row for row in rows if row.verdict == VERDICT_YES]
    errors = [row for row in rows if row.verdict == VERDICT_ERROR]

    lines: list[str] = ["# LongMemEval 채점 리포트", ""]
    lines.append(f"- workspace: {inputs.workspace_id}")
    lines.append(f"- 결과 디렉토리: `{inputs.results_dir}`")
    lines.append(
        f"- 채점 시각: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    )
    lines.append(f"- judge 프롬프트 버전: `{JUDGE_PROMPT_VERSION}`")
    lines.append(
        "- 프롬프트 출처: 공식 `evaluate_qa.py`의 재현이 아니라 그 "
        "유형별 분기 규칙을 이식한 것이다. 원문을 대조하지 못했으므로 "
        "이 점수는 공식 리더보드 값과 직접 비교할 수 없다."
    )
    lines.append("")
    lines.append(
        f"전체 {len(rows)}문항 중 채점 {len(graded)}건, "
        f"정답 {len(correct)}건 "
        f"({_ratio(len(correct), len(graded))}), "
        f"미채점 {len(errors)}건."
    )
    lines.append("")

    lines.append("## 유형별 정답률")
    lines.append("")
    lines.append("| 유형 | 문항 | 정답 | 오답 | 미채점 | 정답률 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    buckets: dict[str, list[GradeRow]] = {}
    for row in rows:
        buckets.setdefault(row.bucket, []).append(row)
    for bucket in sorted(buckets):
        bucket_rows = buckets[bucket]
        yes = sum(1 for row in bucket_rows if row.verdict == VERDICT_YES)
        no = sum(1 for row in bucket_rows if row.verdict == VERDICT_NO)
        err = sum(1 for row in bucket_rows if row.verdict == VERDICT_ERROR)
        lines.append(
            f"| {bucket} | {len(bucket_rows)} | {yes} | {no} | {err} | "
            f"{_ratio(yes, yes + no)} |"
        )
    lines.append("")

    lines.append("## 실패 귀속 분포")
    lines.append("")
    failures = [row for row in rows if row.attribution is not None]
    counts = Counter(
        row.attribution.cause for row in failures if row.attribution
    )
    lines.append("| 대표 원인 | 건수 | 오답 중 비율 |")
    lines.append("| --- | ---: | ---: |")
    for cause in FAILURE_CAUSES:
        lines.append(
            f"| {cause} | {counts.get(cause, 0)} | "
            f"{_ratio(counts.get(cause, 0), len(failures))} |"
        )
    lines.append(f"| (합계) | {len(failures)} | - |")
    lines.append("")
    lines.append(
        "귀속은 상류 우선이다. 한 문항에 증상이 겹치면 위 표의 위쪽 "
        "원인 하나만 대표로 센다."
    )
    lines.append("")

    lines.append("## 진단 한계")
    lines.append("")
    lines.append(
        "위 분포는 정확한 인과 추적이 아니라 근사다. 세 한계 모두 "
        "실패를 실제보다 적게 세는 쪽으로 기울므로, 이 표를 낙관 쪽으로 "
        "더 읽으면 안 된다."
    )
    lines.append("")
    lines.append(
        "1. 문항과 모순 안건은 claim 집합이 겹치는지로만 잇는다. 한 "
        "workspace에 여러 문항의 세션이 섞이므로 다른 문항 때문에 열린 "
        "안건이 이 문항에 잡힐 수 있다. 그래서 `conflict_missed`는 "
        "위음성 쪽으로 기운다 — 실제로 놓친 모순보다 적게 잡힌다."
    )
    lines.append(
        "2. `extracted_claims`는 근거 세션 단위 집계이지 has_answer 턴 "
        "단위가 아니다. 정답과 무관한 다른 턴에서 나온 claim도 세므로 "
        "`claim_not_extracted`는 관대하다 — 실제 추출 실패보다 적게 "
        "잡힌다."
    )
    lines.append(
        "3. QA trace가 승자 claim의 id를 담지 않아, "
        "`adjudication_wrong`은 \"판정 결과가 QA 컨텍스트까지 오지 "
        "않았다\"를 컨텍스트 claim이 0인지로 근사한다. 승자가 아닌 다른 "
        "claim이 실려 있으면 이 규칙은 걸리지 않고 `answer_generation`으로 "
        "흐른다."
    )
    lines.append("")

    lines.append("## 조회 깔때기")
    lines.append("")
    misses = sum(1 for row in rows if row.subject_miss)
    abstains = sum(1 for row in rows if row.abstained)
    no_claims = sum(
        1 for row in rows if row.evidence_stats.extracted_claims == 0
    )
    lines.append("| 지표 | 값 | 비율 |")
    lines.append("| --- | ---: | ---: |")
    lines.append(f"| subject miss | {misses} | {_ratio(misses, len(rows))} |")
    lines.append(
        f"| 근거 세션에서 claim 0 | {no_claims} | "
        f"{_ratio(no_claims, len(rows))} |"
    )
    lines.append(
        f"| QA 거절(abstain) | {abstains} | "
        f"{_ratio(abstains, len(rows))} |"
    )
    lines.append("")

    lines.append("## 모순 감지·판정")
    lines.append("")
    linked = sum(
        1 for row in rows if row.evidence_stats.contradictions_detected > 0
    )
    decided_rows = sum(
        1 for row in rows if row.evidence_stats.contradictions_decided > 0
    )
    lines.append("| 지표 | 값 |")
    lines.append("| --- | ---: |")
    lines.append(f"| workspace 전체 모순 안건 | {inputs.contradiction_total} |")
    lines.append(f"| 그중 결정된 안건 | {inputs.contradiction_decided} |")
    lines.append(f"| 모순 안건이 걸린 문항 | {linked} |")
    lines.append(f"| 그중 결정까지 간 문항 | {decided_rows} |")
    lines.append("")

    lines.append("## 단계별 소요 시간")
    lines.append("")
    lines.append("| 단계 | 초 | 출처 |")
    lines.append("| --- | ---: | --- |")
    lines.append(
        f"| QA 답변 | {inputs.qa_elapsed_ms / 1000:.1f} | "
        f"`{TRACE_FILENAME}`의 문항별 elapsed 합 |"
    )
    lines.append(
        f"| 채점 | {inputs.grade_elapsed_ms / 1000:.1f} | 이번 실행 실측 |"
    )
    lines.append(
        f"| 합계 | "
        f"{(inputs.qa_elapsed_ms + inputs.grade_elapsed_ms) / 1000:.1f} | - |"
    )
    lines.append("")
    lines.append(
        "수집·추출·해소·판정 단계의 시간은 이 리포트가 재지 않는다. "
        "각 러너를 돌린 wall-clock을 실행 기록에서 옮겨 적는다."
    )
    lines.append("")

    judge_usage = inputs.judge_usage
    total_usage = inputs.qa_usage.plus(judge_usage)
    lines.append("## 토큰·비용")
    lines.append("")
    lines.append(
        f"단가: 입력 ${inputs.input_price}/M, 출력 ${inputs.output_price}/M."
    )
    lines.append("")
    lines.append("| 단계 | 호출 | 입력 토큰 | 출력 토큰 | 비용(USD) |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for label, usage in (
        ("QA", inputs.qa_usage),
        ("채점", judge_usage),
        ("합계", total_usage),
    ):
        cost = estimate_cost(
            usage,
            input_price=inputs.input_price,
            output_price=inputs.output_price,
        )
        lines.append(
            f"| {label} | {usage.calls} | {usage.input_tokens} | "
            f"{usage.output_tokens} | {cost:.4f} |"
        )
    lines.append("")
    lines.append(
        "수집·추출·해소 단계의 토큰은 각 러너의 usage JSON에 따로 있다. "
        "전체 실행 비용은 그 값들을 이 표에 더해야 나온다."
    )
    lines.append("")

    lines.append("## 사후 검토 플래그")
    lines.append("")
    lines.append("- 어휘 스냅샷:")
    if not inputs.vocabulary_snapshots:
        lines.append("  - 이 workspace에 claim candidate가 없다.")
    for ontology_id, version, count in inputs.vocabulary_snapshots:
        lines.append(f"  - `{ontology_id}` / `{version}` — candidate {count}건")
    if len(inputs.vocabulary_snapshots) > 1:
        lines.append(
            "  - 경고: 스냅샷이 둘 이상이다. 서로 다른 어휘로 뽑힌 claim이 "
            "섞였으므로 이 점수를 하나의 어휘 아래 해석할 수 없다."
        )
    lines.append(
        "- 어휘 초안은 부트스트랩 workspace에서 만들어 사람이 검토한 뒤 "
        "발행한 것이다. 정답률이 특정 predicate에서만 낮다면 점수보다 "
        "그 스냅샷의 value_type을 먼저 의심한다."
    )
    lines.append(
        "- 판정 규칙은 벤치마크 전용(최근 관찰이 이긴다)이다. 이 값을 "
        "제품의 모순 판정 품질로 읽지 않는다."
    )
    lines.append("")
    return "\n".join(lines)


def _message_text(message: Any) -> str:
    """모델 응답에서 사람이 읽을 본문만 뽑는다.

    Bedrock은 content를 문자열로도 블록 리스트로도 돌려준다. 리스트를
    그대로 문자열로 만들면 첫 단어가 판정이 아니라 JSON 껍데기가 된다.
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type", "text") == "text"
        ]
        return "".join(parts).strip()
    return str(content).strip()


def bedrock_judge(llm: BaseChatModel) -> JudgeFn:
    """Bedrock 모델을 판정 함수로 감싼다."""

    def judge(
        *,
        question: str,
        answer: str,
        hypothesis: str,
        question_type: str,
        is_abstention: bool,
    ) -> JudgeResult:
        message = llm.invoke(
            build_judge_prompt(
                question=question,
                answer=answer,
                hypothesis=hypothesis,
                question_type=question_type,
                is_abstention=is_abstention,
            )
        )
        raw = _message_text(message)
        return JudgeResult(
            verdict=parse_verdict(raw),
            raw=raw,
            usage=usage_from_message(message),
        )

    return judge


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=DEFAULT_WORKSPACE_ID,
        help="진단 근거를 읽어올 평가 workspace를 정한다.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        required=True,
        help="QA 러너가 쓴 결과 디렉토리를 정한다. 산출물도 여기에 쓴다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="채점할 문항 수를 앞에서부터 제한한다. 비용 제어용이다.",
    )
    parser.add_argument("--per-type", type=int, default=10)
    parser.add_argument(
        "--oracle-path",
        type=Path,
        default=DEFAULT_ORACLE_PATH,
    )
    parser.add_argument(
        "--input-price",
        type=float,
        default=DEFAULT_INPUT_PRICE,
        help="입력 토큰 백만 개당 단가(USD)를 정한다.",
    )
    parser.add_argument(
        "--output-price",
        type=float,
        default=DEFAULT_OUTPUT_PRICE,
        help="출력 토큰 백만 개당 단가(USD)를 정한다.",
    )
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    args = parser.parse_args()

    results_path = args.results_dir / RESULTS_FILENAME
    trace_path = args.results_dir / TRACE_FILENAME
    if not results_path.exists():
        raise SystemExit(f"QA 결과 파일이 없다: {results_path}")
    if not args.oracle_path.exists():
        raise SystemExit(f"oracle 파일이 없다: {args.oracle_path}")

    results = read_jsonl(results_path)
    if args.limit is not None:
        results = results[: max(args.limit, 0)]
    if not results:
        raise SystemExit("채점할 답변이 없다.")

    traces = {
        str(row["question_id"]): row
        for row in (read_jsonl(trace_path) if trace_path.exists() else [])
    }
    qa_elapsed_ms = sum(
        float(row.get("elapsed_ms") or 0.0) for row in traces.values()
    )

    subset = select_subset(
        load_oracle(args.oracle_path),
        per_type=args.per_type,
    )
    questions = {question.question_id: question for question in subset}

    qa_usage = UsageTotals()
    usage_path = args.results_dir / USAGE_FILENAME
    if usage_path.exists():
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
        qa_usage = UsageTotals(
            calls=int(payload.get("calls") or 0),
            input_tokens=int(payload.get("input_tokens") or 0),
            output_tokens=int(payload.get("output_tokens") or 0),
        )

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_factory() as session:
            claim_sessions = load_claim_sessions(
                session,
                workspace_id=args.workspace_id,
            )
            proposals = load_contradiction_proposals(
                session,
                workspace_id=args.workspace_id,
            )
            snapshots = load_vocabulary_snapshots(
                session,
                workspace_id=args.workspace_id,
            )
        evidence = build_evidence_stats(
            subset,
            claim_sessions=claim_sessions,
            proposals=proposals,
        )

        service = get_llm_service(
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity(args.capacity),
            streaming=False,
        )
        judge = bedrock_judge(service.get_llm())

        grades_path = args.results_dir / GRADES_FILENAME
        started = time.perf_counter()
        with grades_path.open("w", encoding="utf-8") as grades_file:

            def _record(row: GradeRow) -> None:
                grades_file.write(
                    json.dumps(row.as_dict(), ensure_ascii=False) + "\n"
                )
                grades_file.flush()
                cause = (
                    ""
                    if row.attribution is None
                    else f"  {row.attribution.cause}"
                )
                print(f"  {row.question_id}  {row.verdict.upper()}{cause}")

            rows = grade_questions(
                results,
                questions=questions,
                traces=traces,
                evidence=evidence,
                judge=judge,
                on_row=_record,
            )
        grade_elapsed_ms = (time.perf_counter() - started) * 1000
    finally:
        engine.dispose()

    report_inputs = ReportInputs(
        workspace_id=args.workspace_id,
        results_dir=args.results_dir,
        rows=tuple(rows),
        qa_usage=qa_usage,
        qa_elapsed_ms=qa_elapsed_ms,
        grade_elapsed_ms=grade_elapsed_ms,
        contradiction_total=len(proposals),
        contradiction_decided=sum(1 for p in proposals if p.decided),
        vocabulary_snapshots=tuple(snapshots),
        input_price=args.input_price,
        output_price=args.output_price,
    )
    report_path = args.results_dir / REPORT_FILENAME
    report_path.write_text(render_report(report_inputs), encoding="utf-8")

    judge_usage = report_inputs.judge_usage
    grade_usage_path = args.results_dir / GRADE_USAGE_FILENAME
    grade_usage_path.write_text(
        json.dumps(
            {
                "workspace_id": args.workspace_id,
                "capacity": args.capacity,
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                "graded": len(rows),
                "input_price": args.input_price,
                "output_price": args.output_price,
                "estimated_cost_usd": round(
                    estimate_cost(
                        judge_usage,
                        input_price=args.input_price,
                        output_price=args.output_price,
                    ),
                    6,
                ),
                "elapsed_ms": round(grade_elapsed_ms, 3),
                **judge_usage.as_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    correct = sum(1 for row in rows if row.verdict == VERDICT_YES)
    graded = sum(1 for row in rows if row.verdict != VERDICT_ERROR)
    print(f"\n=== 채점 결과 (ws={args.workspace_id}) ===")
    print(f"  정답 {correct}/{graded}  (미채점 {len(rows) - graded})")
    print(f"  {args.results_dir / GRADES_FILENAME}")
    print(f"  {report_path}")
    print(f"  {grade_usage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
