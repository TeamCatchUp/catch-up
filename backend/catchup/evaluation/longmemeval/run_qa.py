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

결과는 세 파일로 나눠 쓴다. 채점기가 읽을 최소 형태(`qa_results.jsonl`),
왜 그 답이 나왔는지 되짚을 흔적(`qa_trace.jsonl`), 비용 집계
(`qa_usage.json`)다. 한 건이 끝날 때마다 흘려 쓰고 flush하므로 중간에
멈춰도 그때까지의 결과는 남는다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_qa \\
        --output experiments/longmemeval/results/ \\
        --per-type 10
"""

from __future__ import annotations

import argparse
import json
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
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.dataset import load_oracle
from catchup.evaluation.longmemeval.dataset import select_subset
from catchup.evaluation.longmemeval.draft_vocabulary import UsageTotals
from catchup.evaluation.longmemeval.draft_vocabulary import usage_from_message
from catchup.evaluation.longmemeval.qa_service import MAX_SUBJECTS
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import KnowledgeLookup
from catchup.evaluation.longmemeval.qa_service import LookupFor
from catchup.evaluation.longmemeval.qa_service import QuestionOutcome
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import answer_questions
from catchup.evaluation.longmemeval.qa_service import build_answer_prompt
from catchup.evaluation.longmemeval.qa_service import build_subject_prompt
from catchup.evaluation.longmemeval.workspace_manifest import DEFAULT_MANIFEST_PATH
from catchup.evaluation.longmemeval.workspace_manifest import load_manifest
from catchup.evaluation.longmemeval.workspace_manifest import workspace_by_question
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


def _message_text(message: Any) -> str:
    """모델 응답에서 사람이 읽을 본문만 뽑는다.

    Bedrock은 content를 문자열로도, 블록 리스트로도 돌려준다. 리스트일
    때 그대로 문자열로 만들면 답변에 JSON 껍데기가 섞인다.
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
            answer=_message_text(message),
            usage=usage_from_message(message),
        )

    return answer


def postgres_lookup(session_factory, *, workspace_id: int) -> KnowledgeLookup:
    """as-of·history 조회를 실제 DB에 연결한다.

    UnitOfWork를 조회마다 새로 만든다. 하나를 재사용하면 앞 조회의
    session이 이미 닫혀 있어 두 번째 조회가 깨진다.
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
            uow=_uow(),
        )

    def history(subject: str) -> AsOfQueryResult:
        return query_claims_history(
            workspace_id=workspace_id,
            subject=subject,
            uow=_uow(),
        )

    return KnowledgeLookup(as_of=as_of, history=history)


def manifest_lookup_for(
    session_factory,
    *,
    workspace_for: dict[str, int],
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
        )

    return choose


def _write_line(handle: TextIO, payload: dict[str, Any]) -> None:
    """JSONL 한 줄을 쓰고 곧바로 내보낸다."""
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    handle.flush()


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
        help="결과 세 파일을 쓸 디렉토리를 정한다.",
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

    workspace_for: dict[str, int] | None = None
    if args.manifest is not None and args.manifest.exists():
        workspace_for = workspace_by_question(load_manifest(args.manifest))
        check_manifest_covers(
            (question.question_id for question in questions),
            workspace_for,
        )

    args.output.mkdir(parents=True, exist_ok=True)
    results_path = args.output / RESULTS_FILENAME
    trace_path = args.output / TRACE_FILENAME
    usage_path = args.output / USAGE_FILENAME

    service = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity(args.capacity),
        streaming=False,
    )
    llm = service.get_llm()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    total = UsageTotals()
    abstained = 0

    try:
        with (
            results_path.open("w", encoding="utf-8") as results_file,
            trace_path.open("w", encoding="utf-8") as trace_file,
        ):

            def _record(outcome: QuestionOutcome) -> None:
                nonlocal total, abstained
                total = total.plus(outcome.usage)
                if outcome.abstained:
                    abstained += 1
                _write_line(results_file, outcome.result_payload())
                _write_line(trace_file, outcome.trace_payload())
                print(
                    f"  {outcome.question_id}  "
                    f"as_of={outcome.as_of_claims} "
                    f"history={outcome.history_claims}  "
                    f"{'ABSTAIN' if outcome.abstained else 'ANSWER'}"
                )

            if workspace_for is None:
                lookup: KnowledgeLookup | LookupFor = postgres_lookup(
                    session_factory,
                    workspace_id=args.workspace_id,
                )
            else:
                lookup = manifest_lookup_for(
                    session_factory,
                    workspace_for=workspace_for,
                )

            outcomes = answer_questions(
                questions,
                lookup=lookup,
                extract_subjects=bedrock_extract_subjects(llm),
                answer=bedrock_answer(llm),
                on_outcome=_record,
            )
    finally:
        engine.dispose()

    isolated = workspace_for is not None
    usage_path.write_text(
        json.dumps(
            {
                "workspace_id": None if isolated else args.workspace_id,
                "manifest": str(args.manifest) if isolated else None,
                "capacity": args.capacity,
                "questions": len(outcomes),
                "abstained": abstained,
                **total.as_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    scope = (
        f"문항별 격리, manifest={args.manifest}"
        if isolated
        else f"ws={args.workspace_id}"
    )
    print(f"\n=== QA 결과 ({scope}) ===")
    print(f"  문항: {len(outcomes)}  거절: {abstained}")
    print(f"  호출 {total.calls}회, 토큰 {total.total_tokens}")
    print(f"  {results_path}")
    print(f"  {trace_path}")
    print(f"  {usage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
