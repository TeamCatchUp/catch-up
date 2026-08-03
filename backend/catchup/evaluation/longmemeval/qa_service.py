"""저장된 지식만 재료로 LongMemEval 문항에 답한다.

벤치마크가 재려는 것은 모델의 상식이 아니라 파이프라인이 쌓아 둔
지식이다. 그래서 이 모듈은 재료를 먼저 모으고, 재료가 없으면 답을
만들지 않는다 — 컨텍스트가 비면 답변 모델을 아예 부르지 않고 고정
abstention 문구를 쓴다. 빈 컨텍스트를 모델에 넘겨 "모른다고 답하라"고
부탁하는 방식은 부탁일 뿐이라 fail-open이고, 호출 비용도 그만큼 든다.

조회는 둘을 함께 쓴다.

- as-of(`at=question_date`): 질문 시점에 참이었던 것. "지금 어디서
  일하나" 류가 이걸로 답해진다.
- history: 한때 참이었던 것까지. "예전에는 어디였나", "언제 바뀌었나"
  류는 닫힌 구간을 봐야 답이 나온다.

두 결과는 한 텍스트로 합치되 절을 나눈다. 나누지 않으면 모델이 이미
끝난 사실을 현재로 읽는다. history 절에서는 as-of 절에 이미 실린
claim을 빼고, 남은 것(닫힌 구간)만 적는다. 같은 문장을 두 번 실으면
토큰만 늘고 모델은 그것을 두 개의 사실로 오해한다.

subject 추출과 답변 생성은 호출자가 주입한다. 이 모듈은 DB도 LLM도
직접 부르지 않는다. 실제 연결은 `run_qa.py`가 맡는다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.draft_vocabulary import UsageTotals
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult

__all__ = [
    "ABSTENTION_ANSWER",
    "MAX_SUBJECTS",
    "AnswerFn",
    "AnswerResult",
    "ExtractSubjectsFn",
    "KnowledgeLookup",
    "QuestionOutcome",
    "SubjectResult",
    "SubjectTrace",
    "UsageTotals",
    "answer_questions",
    "build_answer_prompt",
    "build_subject_prompt",
    "render_claims_context",
    "run_question",
]

ABSTENTION_ANSWER = "I don't have information about that."
"""근거가 없을 때 쓰는 고정 답변을 나타낸다.

LongMemEval의 abstention 채점은 "모른다고 말했는가"를 본다. 문구가
실행마다 흔들리면 채점자가 같은 판단을 다르게 읽으므로 하나로 고정한다.
"""

MAX_SUBJECTS = 5
"""한 문항에서 조회할 subject 후보의 최대 개수를 나타낸다."""

UNKNOWN_BOUND = "unknown"
"""언제부터 참인지 모르는 구간 시작을 나타낸다."""

OPEN_BOUND = "present"
"""아직 닫히지 않은 구간 끝을 나타낸다."""

SUBJECT_PROMPT_HEADER = f"""\
You are preparing a lookup key for a knowledge base of stored facts.

Read the question and list the entities whose stored facts would answer
it — people, organizations, places, pets, products, or other named
things the question is about.

Rules:
- List at most {MAX_SUBJECTS} entities, most likely first.
- Copy each name as it appears in the question. Do not translate,
  expand, or invent names.
- Prefer the specific thing being asked about over the person asking.
- Use noun phrases only. No verbs, no sentences, no questions.
- If the question names no entity at all, return an empty list.

Question:
"""

ANSWER_PROMPT_TEMPLATE = f"""\
You answer questions using ONLY the stored knowledge given below.

Rules:
- Use nothing but the stored knowledge. Do not use your own world
  knowledge, and do not guess.
- The question is asked on the given date. Facts under "Known as of"
  were true on that date. Facts under "History" were true once and are
  no longer, so use them only for questions about the past or about
  when something changed.
- Each fact shows the period it was true for as (from~to). "{OPEN_BOUND}"
  means it is still true, "{UNKNOWN_BOUND}" means the start is unknown.
- If the stored knowledge does not support an answer, reply exactly:
  {ABSTENTION_ANSWER}
- Answer in one short sentence. No explanation, no citations.

Question date: {{question_date}}

Stored knowledge:
{{claims_context}}

Question: {{question}}
Answer:"""


@dataclass(frozen=True, slots=True)
class SubjectResult:
    """subject 추출 한 번의 결과를 담는다.

    Attributes:
        subjects: 조회에 쓸 대상 후보를 우선순위 순으로 담는다.
        usage: 추출 호출이 쓴 토큰을 담는다.
    """

    subjects: tuple[str, ...] = ()
    usage: UsageTotals = field(default_factory=UsageTotals)


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """답변 생성 한 번의 결과를 담는다.

    Attributes:
        answer: 모델이 쓴 가설 답변을 담는다.
        usage: 답변 호출이 쓴 토큰을 담는다.
    """

    answer: str
    usage: UsageTotals = field(default_factory=UsageTotals)


ExtractSubjectsFn = Callable[[str], SubjectResult]
"""질문 하나에서 subject 후보를 뽑는 함수를 나타낸다."""

AnswerFn = Callable[..., AnswerResult]
"""질문·질문 시각·컨텍스트로 답변을 쓰는 함수를 나타낸다."""

AsOfLookupFn = Callable[[str, datetime], AsOfQueryResult]
"""subject와 시각으로 as-of claim을 읽는 함수를 나타낸다."""

HistoryLookupFn = Callable[[str], AsOfQueryResult]
"""subject로 history claim을 읽는 함수를 나타낸다."""


@dataclass(frozen=True, slots=True)
class KnowledgeLookup:
    """as-of와 history 두 조회 경로를 한 묶음으로 담는다.

    Attributes:
        as_of: 어떤 시점에 참이었던 claim을 읽는다.
        history: 한때 참이었던 claim까지 읽는다.
    """

    as_of: AsOfLookupFn
    history: HistoryLookupFn


@dataclass(frozen=True, slots=True)
class SubjectTrace:
    """subject 후보 하나를 조회한 흔적을 담는다.

    Attributes:
        subject: 조회에 쓴 입력 문자열을 담는다.
        matched: 노드를 찾았는지 나타낸다. False면 miss다.
        matched_by: canonical_key인지 alias인지 나타내고, miss면 None이다.
        display_name: 매칭된 노드의 이름을 담고, miss면 None이다.
        as_of_claims: as-of 조회가 돌려준 claim 수를 나타낸다.
        history_claims: history 조회가 돌려준 claim 수를 나타낸다.
    """

    subject: str
    matched: bool
    matched_by: str | None
    display_name: str | None
    as_of_claims: int
    history_claims: int

    def as_dict(self) -> dict[str, Any]:
        """trace 파일에 담을 형태로 바꾼다."""
        return {
            "subject": self.subject,
            "matched": self.matched,
            "matched_by": self.matched_by,
            "display_name": self.display_name,
            "as_of_claims": self.as_of_claims,
            "history_claims": self.history_claims,
        }


@dataclass(frozen=True, slots=True)
class QuestionOutcome:
    """문항 한 건을 처리한 결과와 그 근거를 담는다.

    Attributes:
        question_id: 채점자가 답을 맞춰 볼 식별자를 나타낸다.
        question_type: 유형별 점수 집계에 쓸 질문 유형을 나타낸다.
        hypothesis: 채점 대상이 될 답변 문장을 담는다.
        abstained: 재료가 없어 거절했는지 나타낸다.
        subjects: subject별 조회 흔적을 시도 순서대로 담는다.
        claims_context: 답변 모델에 넘긴 텍스트를 그대로 담는다.
        usage: 이 문항이 쓴 토큰 합계를 담는다.
        elapsed_ms: 이 문항 처리에 걸린 시간을 밀리초로 담는다.
    """

    question_id: str
    question_type: str
    hypothesis: str
    abstained: bool
    subjects: tuple[SubjectTrace, ...]
    claims_context: str
    usage: UsageTotals
    elapsed_ms: float

    @property
    def as_of_claims(self) -> int:
        """as-of 조회로 모은 claim 총수를 나타낸다."""
        return sum(trace.as_of_claims for trace in self.subjects)

    @property
    def history_claims(self) -> int:
        """history 조회로 모은 claim 총수를 나타낸다."""
        return sum(trace.history_claims for trace in self.subjects)

    def result_payload(self) -> dict[str, Any]:
        """채점자가 읽을 결과 한 줄로 바꾼다."""
        return {"question_id": self.question_id, "hypothesis": self.hypothesis}

    def trace_payload(self) -> dict[str, Any]:
        """왜 그 답이 나왔는지 되짚을 trace 한 줄로 바꾼다."""
        return {
            "question_id": self.question_id,
            "question_type": self.question_type,
            "abstained": self.abstained,
            "subjects_tried": [trace.subject for trace in self.subjects],
            "subjects": [trace.as_dict() for trace in self.subjects],
            "subject_miss": all(
                not trace.matched for trace in self.subjects
            ),
            "as_of_claims": self.as_of_claims,
            "history_claims": self.history_claims,
            "context_chars": len(self.claims_context),
            "elapsed_ms": round(self.elapsed_ms, 3),
            "usage": self.usage.as_dict(),
        }


def _format_bound(moment: datetime | None, *, fallback: str) -> str:
    """구간 경계 하나를 사람이 읽을 문자열로 만든다.

    None을 임의의 시각으로 메우지 않는다. "모른다"와 "안 끝났다"는
    답에 필요한 정보라서 그대로 드러내야 한다.
    """
    return fallback if moment is None else moment.isoformat()


def _format_value(value: object) -> str:
    """claim 값 하나를 한 줄에 실을 문자열로 만든다."""
    text = value if isinstance(value, str) else str(value)
    return " ".join(text.split())


def render_claim_line(claim: AsOfClaim) -> str:
    """claim 하나를 `[predicate] value (구간) — 문장` 한 줄로 만든다."""
    span = (
        f"{_format_bound(claim.valid_from, fallback=UNKNOWN_BOUND)}"
        f"~{_format_bound(claim.valid_to, fallback=OPEN_BOUND)}"
    )
    line = f"- [{claim.predicate}] {_format_value(claim.value)} ({span})"
    statement = " ".join((claim.statement or "").split())
    if statement:
        line = f"{line} — {statement}"
    return line


def render_claims_context(
    lookups: Iterable[tuple[str, AsOfQueryResult, AsOfQueryResult]],
    *,
    as_of: datetime,
) -> str:
    """subject별 as-of·history 결과를 하나의 텍스트로 편다.

    subject마다 절을 나누고, 그 안을 다시 as-of와 history로 나눈다.
    history 절에는 as-of 절에 이미 실린 claim을 넣지 않는다. 남는 것은
    이미 닫힌 구간뿐이라, 모델이 "지금 참"과 "한때 참"을 줄 단위로
    구분할 수 있다.

    claim이 하나도 없는 subject는 통째로 뺀다. 이름만 적힌 빈 절은
    모델에게 "그 대상은 아는데 사실이 없다"로 읽혀 없는 답을 지어낼
    빌미가 된다.
    """
    blocks: list[str] = []
    for subject, as_of_result, history_result in lookups:
        seen = {claim.claim_id for claim in as_of_result.claims}
        closed = tuple(
            claim
            for claim in history_result.claims
            if claim.claim_id not in seen
        )
        if not as_of_result.claims and not closed:
            continue

        matched = as_of_result.subject or history_result.subject
        label = subject
        if matched is not None and matched.display_name:
            if matched.display_name != subject:
                label = f"{subject} (stored as {matched.display_name})"
        lines = [f"## {label}"]
        if as_of_result.claims:
            lines.append(f"### Known as of {as_of.isoformat()}")
            lines.extend(
                render_claim_line(claim) for claim in as_of_result.claims
            )
        if closed:
            lines.append("### History (no longer true)")
            lines.extend(render_claim_line(claim) for claim in closed)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_subject_prompt(question: str) -> str:
    """질문에서 subject 후보를 뽑게 할 프롬프트를 만든다."""
    return f"{SUBJECT_PROMPT_HEADER}{question}\n"


def build_answer_prompt(
    *,
    question: str,
    question_date: datetime,
    claims_context: str,
) -> str:
    """저장된 지식만으로 답하게 할 프롬프트를 만든다."""
    return ANSWER_PROMPT_TEMPLATE.format(
        question_date=question_date.isoformat(),
        claims_context=claims_context,
        question=question,
    )


def normalize_subjects(
    subjects: Iterable[str],
    *,
    limit: int = MAX_SUBJECTS,
) -> tuple[str, ...]:
    """subject 후보를 다듬어 조회할 목록으로 확정한다.

    빈 문자열을 버리고, 같은 이름을 두 번 조회하지 않으며, 앞에서부터
    `limit`개만 남긴다. 모델이 우선순위 순으로 냈다고 보고 순서를
    유지한다.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in subjects:
        subject = raw.strip()
        if not subject:
            continue
        key = subject.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(subject)
        if len(ordered) >= limit:
            break
    return tuple(ordered)


def run_question(
    question: OracleQuestion,
    *,
    lookup: KnowledgeLookup,
    extract_subjects: ExtractSubjectsFn,
    answer: AnswerFn,
    max_subjects: int = MAX_SUBJECTS,
) -> QuestionOutcome:
    """문항 하나를 저장된 지식만으로 답한다.

    순서는 subject 추출 → 이중 조회 → 컨텍스트 렌더 → 답변이다.
    컨텍스트가 비면 마지막 단계를 건너뛰고 고정 abstention을 쓴다.
    재료가 없는데도 모델을 부르면 그 답은 저장된 지식이 아니라 모델의
    사전 지식에서 나온 것이라 벤치마크가 재려는 값을 오염시킨다.
    """
    started = time.perf_counter()

    extraction = extract_subjects(question.question)
    usage = extraction.usage
    subjects = normalize_subjects(extraction.subjects, limit=max_subjects)

    traces: list[SubjectTrace] = []
    lookups: list[tuple[str, AsOfQueryResult, AsOfQueryResult]] = []
    for subject in subjects:
        as_of_result = lookup.as_of(subject, question.question_date)
        history_result = lookup.history(subject)
        matched = as_of_result.subject or history_result.subject
        traces.append(
            SubjectTrace(
                subject=subject,
                matched=matched is not None,
                matched_by=None if matched is None else matched.matched_by,
                display_name=(
                    None if matched is None else matched.display_name
                ),
                as_of_claims=len(as_of_result.claims),
                history_claims=len(history_result.claims),
            )
        )
        lookups.append((subject, as_of_result, history_result))

    claims_context = render_claims_context(
        lookups,
        as_of=question.question_date,
    )

    if claims_context:
        answered = answer(
            question=question.question,
            question_date=question.question_date,
            claims_context=claims_context,
        )
        hypothesis = answered.answer.strip() or ABSTENTION_ANSWER
        usage = usage.plus(answered.usage)
        abstained = hypothesis == ABSTENTION_ANSWER
    else:
        hypothesis = ABSTENTION_ANSWER
        abstained = True

    return QuestionOutcome(
        question_id=question.question_id,
        question_type=question.question_type,
        hypothesis=hypothesis,
        abstained=abstained,
        subjects=tuple(traces),
        claims_context=claims_context,
        usage=usage,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def answer_questions(
    questions: Sequence[OracleQuestion],
    *,
    lookup: KnowledgeLookup,
    extract_subjects: ExtractSubjectsFn,
    answer: AnswerFn,
    max_subjects: int = MAX_SUBJECTS,
    on_outcome: Callable[[QuestionOutcome], None] | None = None,
) -> list[QuestionOutcome]:
    """문항 목록을 입력 순서대로 처리한다.

    `on_outcome`은 한 건이 끝날 때마다 불린다. 긴 실행 도중 진행 상황을
    보여주거나 중간 결과를 흘려 쓰는 데 쓴다.
    """
    outcomes: list[QuestionOutcome] = []
    for question in questions:
        outcome = run_question(
            question,
            lookup=lookup,
            extract_subjects=extract_subjects,
            answer=answer,
            max_subjects=max_subjects,
        )
        outcomes.append(outcome)
        if on_outcome is not None:
            on_outcome(outcome)
    return outcomes
