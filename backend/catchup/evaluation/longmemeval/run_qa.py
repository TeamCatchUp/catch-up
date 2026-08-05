"""LongMemEval 평가 서브셋에 저장된 지식으로 답한다.

`qa_service`가 정한 순서(subject 추출 → as-of·history 이중 조회 →
컨텍스트 렌더 → 답변 또는 거절)를 실제 DB와 Bedrock에 연결한다. 판단
규칙은 전부 `qa_service`에 있고 이 모듈은 배선과 파일 쓰기만 한다.

조회는 쓰지 않는다. `KnowledgeMaintenanceUnitOfWork`를 문항마다 새로
열고 commit 없이 빠져나간다. 평가가 지식 상태를 건드리면 같은 실행을
두 번 돌린 결과가 달라진다.

어느 workspace를 읽을지는 수집 러너가 쓴 manifest가 정한다. 문항마다
haystack이 따로 격리되어 있으므로 조회도 문항마다 자기 workspace로만
간다. manifest가 없으면 `--workspace-id` 하나로 전부 읽던 옛 방식으로
돌아간다 — 격리 이전에 쌓아 둔 workspace를 다시 재볼 수 있어야 한다.

subject 정확 일치가 빗나갔을 때 이름이 비슷한 후보를 되짚을지는
`--similarity-fallback`이 정한다. 기본은 on이고, off는 되짚기가 점수를
얼마나 움직였는지 재기 위한 기준선이다. 어느 쪽으로 돌았는지는
`qa_usage.json`에 남는다 — 두 실행의 점수를 나란히 놓고 볼 때 그 값이
없으면 어느 쪽이 기준선인지 알 수 없다.

결과는 세 파일로 나눠 쓴다. 채점기가 읽을 최소 형태(`qa_results.jsonl`),
왜 그 답이 나왔는지 되짚을 흔적(`qa_trace.jsonl`), 비용 집계
(`qa_usage.json`)다. 세 파일 모두 실행 전용 디렉토리
`<output>/runs/<run_id>/`에 쓰고, 전 문항이 성공한 뒤에야 포인터 파일
`<output>/current_run.json`이 그 run을 완주본으로 가리킨다. 부분 결과를
완주본으로 가리키면 채점기가 줄어든 분모 위에서 점수를 낸다 — 어려운
문항에서 깨진 실행일수록 점수가 오히려 높아진다. 세 파일을 하나씩 최종
경로로 옮기지 않는 이유도 같다. 파일별 교체는 같은 출력 디렉토리로 도는
두 실행의 결과·trace·usage를 섞어 놓는다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_qa \\
        --output experiments/longmemeval/results/ \\
        --per-type 10
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import TextIO

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.evaluation.longmemeval.atomic_publish import pointer_path
from catchup.evaluation.longmemeval.atomic_publish import staged_outputs
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.dataset import load_oracle
from catchup.evaluation.longmemeval.dataset import select_subset
from catchup.evaluation.longmemeval.qa_service import MAX_SUBJECTS
from catchup.evaluation.longmemeval.qa_service import AnswerFn
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import ExtractSubjectsFn
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import LookupFor
from catchup.evaluation.longmemeval.qa_service import QuestionOutcome
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import answer_questions
from catchup.evaluation.longmemeval.qa_service import build_answer_prompt
from catchup.evaluation.longmemeval.qa_service import build_subject_prompt
from catchup.evaluation.longmemeval.usage import UsageTotals
from catchup.evaluation.longmemeval.usage import message_text
from catchup.evaluation.longmemeval.usage import usage_from_message
from catchup.evaluation.longmemeval.workspace_manifest import DEFAULT_MANIFEST_PATH
from catchup.evaluation.longmemeval.workspace_manifest import resolve_workspace_for
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import AsOfQueryResult
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_history,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_of_node,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_of_node_history,
)

DEFAULT_WORKSPACE_ID = 902
DEFAULT_ORACLE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "experiments"
    / "longmemeval"
    / "longmemeval_oracle.json"
)
RESULTS_FILENAME = "qa_results.jsonl"
TRACE_FILENAME = "qa_trace.jsonl"
USAGE_FILENAME = "qa_usage.json"

SHARED_WORKSPACE_EVENT = "bench_qa_shared_workspace"
"""manifest 없이 공용 workspace로 조회할 때 남길 로그 이름을 나타낸다."""


class SubjectCandidates(BaseModel):
    """질문에서 뽑은 조회 대상 후보를 담는다."""

    model_config = ConfigDict(extra="forbid")

    subjects: list[str] = Field(
        default_factory=list,
        description=(
            f"Entity names to look up, at most {MAX_SUBJECTS}, "
            f"most likely first."
        ),
    )


def bedrock_extract_subjects(llm: BaseChatModel):
    """Bedrock 모델을 subject 추출 함수로 감싼다.

    `include_raw=True`로 받는다. 파싱된 결과만 받으면 토큰을 셀 수 없고,
    이 러너는 문항당 비용을 남기는 것이 요건이기 때문이다. 구조화 출력이
    깨지면 멈추지 않고 빈 후보로 넘긴다 — 후보가 없으면 뒤 단계가
    abstention으로 닫히므로 fail-closed가 유지된다.
    """
    structured = llm.with_structured_output(
        SubjectCandidates,
        method="function_calling",
        include_raw=True,
    )

    def extract(question: str) -> SubjectResult:
        result = structured.invoke(build_subject_prompt(question))
        parsed = result.get("parsed")
        usage = usage_from_message(result.get("raw"))
        if parsed is None:
            return SubjectResult(subjects=(), usage=usage)
        return SubjectResult(subjects=tuple(parsed.subjects), usage=usage)

    return extract


def bedrock_answer(llm: BaseChatModel):
    """Bedrock 모델을 답변 함수로 감싼다."""

    def answer(
        *,
        question: str,
        question_date: datetime,
        claims_context: str,
    ) -> AnswerResult:
        message = llm.invoke(
            build_answer_prompt(
                question=question,
                question_date=question_date,
                claims_context=claims_context,
            )
        )
        return AnswerResult(
            answer=message_text(message),
            usage=usage_from_message(message),
        )

    return answer


def postgres_lookup(
    session_factory,
    *,
    workspace_id: int,
    include_similar: bool = True,
) -> KnowledgeLookup:
    """이름·node id 네 조회 경로를 실제 DB에 연결한다.

    UnitOfWork를 조회마다 새로 만든다. 하나를 재사용하면 앞 조회의
    session이 이미 닫혀 있어 두 번째 조회가 깨진다.

    `include_similar`는 이름 조회에만 건다. 끄면 정확 매칭이 빗나가도
    유사 후보 SQL을 아예 돌리지 않으므로, 되짚기를 끈 실행이 그 조회
    비용까지 빼고 도는 진짜 기준선이 된다. node id 조회는 애초에
    후보를 찾지 않아 이 스위치와 무관하다.
    """

    def _uow() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory,
            workspace_id=workspace_id,
        )

    def as_of(subject: str, at: datetime) -> AsOfQueryResult:
        return query_claims_as_of(
            workspace_id=workspace_id,
            subject=subject,
            at=at,
            include_similar=include_similar,
            uow=_uow(),
        )

    def history(subject: str) -> AsOfQueryResult:
        return query_claims_history(
            workspace_id=workspace_id,
            subject=subject,
            include_similar=include_similar,
            uow=_uow(),
        )

    def as_of_node(node_id: uuid.UUID, at: datetime) -> AsOfQueryResult:
        return query_claims_of_node(
            workspace_id=workspace_id,
            node_id=node_id,
            at=at,
            uow=_uow(),
        )

    def history_node(node_id: uuid.UUID) -> AsOfQueryResult:
        return query_claims_of_node_history(
            workspace_id=workspace_id,
            node_id=node_id,
            uow=_uow(),
        )

    return KnowledgeLookup(
        as_of=as_of,
        history=history,
        as_of_node=as_of_node,
        history_node=history_node,
    )


def manifest_lookup_for(
    session_factory,
    *,
    workspace_for: dict[str, int],
    include_similar: bool = True,
) -> LookupFor:
    """문항마다 자기 workspace를 읽는 조회 경로를 고른다.

    manifest에 없는 문항은 `check_manifest_covers`가 앞서 걸러 낸다.
    여기서 기본 workspace로 되돌리면 그 문항만 남의 기억을 보게 되므로
    KeyError로 터지는 편이 낫다.
    """

    def choose(question: OracleQuestion) -> KnowledgeLookup:
        return postgres_lookup(
            session_factory,
            workspace_id=workspace_for[question.question_id],
            include_similar=include_similar,
        )

    return choose


def _write_line(handle: TextIO, payload: dict[str, Any]) -> None:
    """JSONL 한 줄을 쓰고 곧바로 내보낸다."""
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    handle.flush()


def _with_fallback(exact: int, fallback: int) -> str:
    """정확 매칭 수와 되짚기 몫을 한 칸에 적는다.

    되짚기로만 재료를 채운 문항은 정확 매칭 수가 0이다. 그 0만 찍으면
    진행 출력이 "재료가 없었다"로 읽히므로 되짚은 몫을 괄호로 덧붙인다.
    """
    if not fallback:
        return str(exact)
    return f"{exact}(+{fallback} fallback)"


def usage_payload(
    *,
    workspace_id: int | None,
    manifest: Path | None,
    capacity: str,
    questions: int,
    abstained: int,
    total: UsageTotals,
    similarity_fallback: bool = True,
) -> str:
    """비용 집계 파일에 쓸 JSON 본문을 만든다."""
    return (
        json.dumps(
            {
                "workspace_id": workspace_id,
                "manifest": None if manifest is None else str(manifest),
                "capacity": capacity,
                "questions": questions,
                "abstained": abstained,
                "similarity_fallback": similarity_fallback,
                **total.as_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


@dataclass(frozen=True, slots=True)
class QaRunSummary:
    """완주한 실행 하나가 남긴 요약을 담는다.

    Attributes:
        questions: 답을 낸 문항 수를 나타낸다.
        abstained: 그중 거절로 닫은 문항 수를 나타낸다.
        usage: 실행 전체가 쓴 토큰 집계를 나타낸다.
        run_directory: 세 산출물이 놓인 이번 run의 디렉토리를 나타낸다.
        published: 포인터가 이 run을 완주본으로 가리키게 됐는지를
            나타낸다. 더 최신 실행이 포인터를 가져갔으면 False다.
    """

    questions: int
    abstained: int
    usage: UsageTotals
    run_directory: Path
    published: bool


def run_and_publish(
    questions: Sequence[OracleQuestion],
    *,
    lookup: KnowledgeLookup | LookupFor,
    extract_subjects: ExtractSubjectsFn,
    answer: AnswerFn,
    output: Path,
    workspace_id: int | None,
    manifest: Path | None,
    capacity: str,
    use_similarity_fallback: bool = True,
) -> QaRunSummary:
    """전 문항을 답하고, 다 끝났을 때만 이번 run을 완주본으로 세운다.

    문항 하나가 깨지면 예외가 그대로 올라가고 포인터는 `running`에 멈춘다.
    부분 결과가 완주본으로 읽히면 채점기가 그 위에서 점수를 낸다 — 이
    함수의 존재 이유가 그 연결을 끊는 것이다.

    전 문항을 답했더라도 더 최신 실행이 포인터를 가져갔으면 이 run은
    현재가 아니다. 그 사실을 요약의 `published`로 넘겨 호출한 쪽이 성공과
    구분하게 한다.
    """
    total = UsageTotals()
    abstained = 0

    with staged_outputs(
        output,
        (RESULTS_FILENAME, TRACE_FILENAME, USAGE_FILENAME),
    ) as staged:
        results_temp, trace_temp, usage_temp = staged.paths
        with (
            results_temp.open("w", encoding="utf-8") as results_file,
            trace_temp.open("w", encoding="utf-8") as trace_file,
        ):

            def _record(outcome: QuestionOutcome) -> None:
                nonlocal total, abstained
                total = total.plus(outcome.usage)
                if outcome.abstained:
                    abstained += 1
                _write_line(results_file, outcome.result_payload())
                _write_line(trace_file, outcome.trace_payload())
                as_of = _with_fallback(
                    outcome.as_of_claims,
                    outcome.fallback_as_of_claims,
                )
                history = _with_fallback(
                    outcome.history_claims,
                    outcome.fallback_history_claims,
                )
                print(
                    f"  {outcome.question_id}  "
                    f"as_of={as_of} history={history}  "
                    f"{'ABSTAIN' if outcome.abstained else 'ANSWER'}"
                )

            outcomes = answer_questions(
                questions,
                lookup=lookup,
                extract_subjects=extract_subjects,
                answer=answer,
                use_similarity_fallback=use_similarity_fallback,
                on_outcome=_record,
            )

        usage_temp.write_text(
            usage_payload(
                workspace_id=workspace_id,
                manifest=manifest,
                capacity=capacity,
                questions=len(outcomes),
                abstained=abstained,
                total=total,
                similarity_fallback=use_similarity_fallback,
            ),
            encoding="utf-8",
        )

    return QaRunSummary(
        questions=len(outcomes),
        abstained=abstained,
        usage=total,
        run_directory=staged.directory,
        published=not staged.taken_over,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=DEFAULT_WORKSPACE_ID,
        help=(
            "manifest가 없을 때 지식을 읽어올 단일 workspace를 정한다. "
            "manifest가 있으면 그쪽이 문항별 workspace를 정한다."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help=(
            "수집 러너가 쓴 문항-workspace 대응표를 정한다. 파일이 없으면 "
            "`--workspace-id` 하나로 전부 읽는 옛 방식으로 돈다."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=(
            "산출물 루트 디렉토리를 정한다. 세 파일은 그 아래 "
            "`runs/<run_id>/`에 놓이고, 완주하면 `current_run.json`이 "
            "그 run을 가리킨다. 채점기에는 이 루트를 넘긴다."
        ),
    )
    parser.add_argument("--per-type", type=int, default=10)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 문항 수를 앞에서부터 제한한다. 스모크와 비용 제어용이다.",
    )
    parser.add_argument(
        "--oracle-path",
        type=Path,
        default=DEFAULT_ORACLE_PATH,
    )
    parser.add_argument(
        "--similarity-fallback",
        choices=["on", "off"],
        default="on",
        help=(
            "subject 정확 일치가 빗나갔을 때 이름이 비슷한 후보를 그 "
            "canonical 이름으로 다시 조회할지 정한다(기본 on). off는 "
            "되짚기가 점수를 얼마나 움직였는지 재기 위한 기준선 측정용이고, "
            "그때는 후보 재조회를 아예 하지 않는다."
        ),
    )
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    args = parser.parse_args()

    if not args.oracle_path.exists():
        raise SystemExit(f"oracle 파일이 없다: {args.oracle_path}")

    questions = select_subset(
        load_oracle(args.oracle_path),
        per_type=args.per_type,
    )
    if args.limit is not None:
        questions = questions[: max(args.limit, 0)]
    if not questions:
        raise SystemExit("답할 문항이 없다.")

    workspace_for = resolve_workspace_for(
        args.manifest,
        (question.question_id for question in questions),
        event=SHARED_WORKSPACE_EVENT,
    )

    args.output.mkdir(parents=True, exist_ok=True)

    service = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity(args.capacity),
        streaming=False,
    )
    llm = service.get_llm()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    isolated = workspace_for is not None
    use_fallback = args.similarity_fallback == "on"
    if workspace_for is None:
        lookup: KnowledgeLookup | LookupFor = postgres_lookup(
            session_factory,
            workspace_id=args.workspace_id,
            include_similar=use_fallback,
        )
    else:
        lookup = manifest_lookup_for(
            session_factory,
            workspace_for=workspace_for,
            include_similar=use_fallback,
        )

    try:
        summary = run_and_publish(
            questions,
            lookup=lookup,
            extract_subjects=bedrock_extract_subjects(llm),
            answer=bedrock_answer(llm),
            output=args.output,
            workspace_id=None if isolated else args.workspace_id,
            manifest=args.manifest if isolated else None,
            capacity=args.capacity,
            use_similarity_fallback=use_fallback,
        )
    finally:
        engine.dispose()

    scope = (
        f"문항별 격리, manifest={args.manifest}"
        if isolated
        else f"ws={args.workspace_id}"
    )
    print(f"\n=== QA 결과 ({scope}) ===")
    print(f"  문항: {summary.questions}  거절: {summary.abstained}")
    print(f"  유사 후보 되짚기: {args.similarity_fallback}")
    print(
        f"  호출 {summary.usage.calls}회, "
        f"토큰 {summary.usage.total_tokens}"
    )
    print(f"  run 디렉토리: {summary.run_directory}")
    print(f"    {RESULTS_FILENAME}, {TRACE_FILENAME}, {USAGE_FILENAME}")
    print(f"  포인터: {pointer_path(args.output)}")
    if not summary.published:
        # 문항은 다 답했지만 이 run은 현재가 아니다. exit 0으로 끝내면
        # 사람이나 자동화가 이어서 채점을 돌리고, 그 채점은 이 run이
        # 아니라 포인터를 가져간 다른 run을 읽는다.
        print("  이 run은 현재로 공개되지 않았다 (더 최신 실행이 시작됨)")
        print(
            f"  결과는 {summary.run_directory}에 보존, "
            "채점 대상은 다른 run이다"
        )
        return 1
    print(f"  채점: --results-dir {args.output} (포인터가 이 run을 가리킨다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
