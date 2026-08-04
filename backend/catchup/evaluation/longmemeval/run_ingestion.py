"""LongMemEval 세션을 knowledge_maintenance 파이프라인에 밀어 넣는다.

`run_ingestion_pipeline.py`가 ChannelTalk payload로 하는 일을 LongMemEval
세션으로 한다. oracle 파일에서 세션을 골라 `SourceChangeEnvelope`로 감싸고
T1(원문 + Observation + 큐 지시)을 확정한다. 그다음 단계인 추출은
`run_extraction_pipeline.py`가 이어받는다.

모드는 둘이다.

- `eval`: 평가 서브셋(`select_subset`)의 문항마다 전용 workspace를 하나씩
  두고 그 문항의 세션만 넣는다. 한 workspace에 다 부으면 문항 A의 세션에서
  나온 지식이 문항 B의 조회에 걸려, B가 "모른다"고 답해야 맞는 자리에서
  A의 사실로 답하게 된다. 세션이 여러 문항에 겹쳐 나오면 각 문항의
  workspace에 각각 넣는다 — 격리가 목적이므로 중복 적재가 정답이다.
- `bootstrap`: 서브셋 밖 세션(`bootstrap_sessions`)만 넣는다. 어휘 튜닝용
  재료일 뿐 조회 대상이 아니라 격리할 것이 없으므로 workspace 하나를
  쓴다. 평가 대상과 섞이면 안 되므로 그 하나를 반드시 따로 준다.

eval 모드의 workspace 번호는 `--workspace-base`(기본 910000)에 서브셋 안의
인덱스를 더한 값이다. 인덱스는 `select_subset` 순서라 같은 입력이면 늘 같은
번호가 나오고, 재실행이 같은 곳을 덮어쓴다. 어느 문항이 어디에 들어갔는지는
manifest JSON에 적어 QA·채점 러너가 읽는다.

`workspaces` 테이블에는 FK가 걸려 있어 행이 먼저 있어야 한다. 그래서 적재
전에 `ensure_workspace`가 행을 만들어 둔다.

같은 세션을 다시 넣어도 idempotency key로 재사용되므로 여러 번 돌려도
안전하다. 그 키의 UNIQUE는 workspace 단위라 문항별 중복 적재를 막지 않는다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_ingestion \\
        --mode eval --per-type 10
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.longmemeval.dataset import OracleSession
from catchup.evaluation.longmemeval.dataset import bootstrap_sessions
from catchup.evaluation.longmemeval.dataset import load_oracle
from catchup.evaluation.longmemeval.dataset import select_subset
from catchup.evaluation.longmemeval.workspace_manifest import DEFAULT_MANIFEST_PATH
from catchup.evaluation.longmemeval.workspace_manifest import DEFAULT_WORKSPACE_BASE
from catchup.evaluation.longmemeval.workspace_manifest import assign_workspaces
from catchup.evaluation.longmemeval.workspace_manifest import write_manifest
from catchup.knowledge_maintenance.adapters.connectors.longmemeval.observation_normalizer import (  # noqa: E501
    LONGMEMEVAL_SESSION_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.connectors.longmemeval.observation_normalizer import (  # noqa: E501
    LongMemEvalSessionNormalizer,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.contracts.source_change import SourceIdentityPayload
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.services.ingest_and_normalize import (
    ingest_and_normalize,
)

DEFAULT_ORACLE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "experiments"
    / "longmemeval"
    / "longmemeval_oracle.json"
)
SOURCE_TYPE = "longmemeval"
SCOPE_ID = "longmemeval"
ENTITY_TYPE = "session"
EVAL_WORKSPACE_ID = 902
"""평가 전용 workspace 식별자를 나타낸다. bootstrap은 여기 못 넣는다."""

TEMPLATE_WORKSPACE_ID = 1
"""company_id를 베껴 올 기준 workspace를 나타낸다.

문항별 workspace는 사람이 만든 것이 아니라 러너가 찍어 내는 것이라 소속
회사를 정해 줄 사람이 없다. 개발 DB에 늘 있는 1번의 값을 그대로 쓴다.
"""

ENSURE_WORKSPACE_SQL = text(
    """
    INSERT INTO workspaces (id, name, company_id)
    SELECT :workspace_id, :name, company_id
    FROM workspaces
    WHERE id = :template_workspace_id
    ON CONFLICT (id) DO NOTHING
    """
)

WORKSPACE_EXISTS_SQL = text(
    "SELECT 1 FROM workspaces WHERE id = :workspace_id"
)


def ensure_workspace(
    session: Session,
    *,
    workspace_id: int,
    name: str,
    template_workspace_id: int = TEMPLATE_WORKSPACE_ID,
) -> None:
    """문항용 workspace 행을 만들어 둔다. 이미 있으면 그대로 둔다.

    수집 대상 테이블이 `workspaces`를 FK로 참조하므로 행이 없으면 적재가
    통째로 깨진다. 이름은 덮어쓰지 않는다 — 재실행이 사람이 고친 이름을
    되돌리면 안 되고, 문항과 workspace를 잇는 것은 이름이 아니라
    manifest이기 때문이다.

    Raises:
        SystemExit: 기준 workspace가 없어 행을 만들지 못했을 때 낸다.
            조용히 넘어가면 그다음 적재가 FK 오류로 무너지고, 원인이
            여기였다는 사실이 드러나지 않는다.
    """
    session.execute(
        ENSURE_WORKSPACE_SQL,
        {
            "workspace_id": workspace_id,
            "name": name,
            "template_workspace_id": template_workspace_id,
        },
    )
    session.commit()
    exists = session.execute(
        WORKSPACE_EXISTS_SQL,
        {"workspace_id": workspace_id},
    ).first()
    if exists is None:
        raise SystemExit(
            f"workspace {workspace_id}를 만들지 못했다. company_id를 베껴 올 "
            f"기준 workspace({template_workspace_id})가 DB에 없다."
        )


def check_bootstrap_workspace(mode: str, workspace_id: int) -> None:
    """bootstrap 모드가 평가 workspace를 겨냥하면 막는다.

    부트스트랩 세션은 어휘 튜닝용이라 평가 대상 밖에서 고른 것이다.
    이 세션이 평가 workspace에 섞이면 채점기는 아무 오류도 보지 못한
    채 오염된 지식 위에서 점수를 낸다 — 벤치마크가 조용히 무효가 된다.
    되돌리기도 어려우므로 실행 전에 끊는다.

    Raises:
        SystemExit: bootstrap 모드인데 workspace가 평가용일 때 낸다.
    """
    if mode != "bootstrap":
        return
    if workspace_id != EVAL_WORKSPACE_ID:
        return
    raise SystemExit(
        f"bootstrap 모드는 평가 workspace({EVAL_WORKSPACE_ID})에 "
        "넣을 수 없다. 부트스트랩 세션이 평가 지식에 섞이면 벤치마크가 "
        "조용히 무효가 된다. `--workspace-id 901` 등 별도 workspace를 "
        "지정하라."
    )


def session_content(session: OracleSession) -> str:
    """세션 하나를 normalizer가 읽을 JSON 본문으로 직렬화한다.

    `has_answer`는 담지 않는다. 정답 근거 표시는 채점자만 알아야 하며,
    파이프라인 본문에 실리면 추출이 정답을 넘겨다보게 된다.
    """
    return json.dumps(
        {
            "session_id": session.session_id,
            "timestamp": session.timestamp.isoformat(),
            "turns": [
                {"role": turn.role, "content": turn.content}
                for turn in session.turns
            ],
        },
        ensure_ascii=False,
    )


def session_envelope(
    session: OracleSession,
    *,
    workspace_id: int,
) -> SourceChangeEnvelope:
    """세션 하나를 poller가 만들었을 envelope로 감싼다.

    `observed_at`은 실행 시각이 아니라 세션 시각이다. 벤치마크는 과거의
    대화를 다시 재생하는 것이므로, 수집 시각을 지금으로 찍으면 시간 축이
    전부 오늘로 몰린다.

    idempotency key는 세션 식별자로만 만든다. 같은 세션을 몇 번 넣어도
    원문이 한 번만 저장되어야 재실행이 안전하다. 그 키의 UNIQUE는
    workspace 단위(`uq_source_versions_workspace_idempotency_key`)라, 여러
    문항에 겹치는 세션을 문항별 workspace에 각각 넣는 것은 막지 않는다.
    """
    return SourceChangeEnvelope(
        schema_version=1,
        event_id=f"{session.session_id}-created",
        workspace_id=workspace_id,
        source_type=SOURCE_TYPE,
        source_identity=SourceIdentityPayload(
            entity_type=ENTITY_TYPE,
            scope_id=SCOPE_ID,
            target_id=SCOPE_ID,
            external_document_id=session.session_id,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        content=session_content(session),
        content_type=LONGMEMEVAL_SESSION_MEDIA_TYPE,
        observed_at=session.timestamp,
        idempotency_key=f"{session.session_id}-1",
    )


def _ingest_one(
    session: OracleSession,
    *,
    workspace_id: int,
    normalizer: LongMemEvalSessionNormalizer,
    session_factory: sessionmaker,
    summary: dict[str, int],
    prefix: str = "",
) -> None:
    """세션 하나를 정해진 workspace에 넣고 결과를 집계에 더한다."""
    result = ingest_and_normalize(
        session_envelope(session, workspace_id=workspace_id),
        normalizer=normalizer,
        uow=KnowledgeMaintenanceUnitOfWork(session_factory),
    )
    label = f"{result.ingestion.value}/{result.normalization.value}"
    summary[label] = summary.get(label, 0) + 1
    print(
        f"  {prefix}{session.session_id}  {label}  "
        f"observation {str(result.observation_id)[:8]}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=EVAL_WORKSPACE_ID,
        help=(
            "bootstrap 모드가 쓸 workspace를 정한다. eval 모드는 문항마다 "
            "workspace를 따로 쓰므로 이 값을 보지 않는다."
        ),
    )
    parser.add_argument(
        "--workspace-base",
        type=int,
        default=DEFAULT_WORKSPACE_BASE,
        help=(
            "eval 모드에서 문항별 workspace 번호의 시작점을 정한다. "
            "실제 번호는 여기에 서브셋 안의 인덱스를 더한 값이다."
        ),
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="eval 모드에서 문항-workspace 대응표를 쓸 경로를 정한다.",
    )
    parser.add_argument(
        "--mode",
        choices=("eval", "bootstrap"),
        default="eval",
    )
    parser.add_argument("--per-type", type=int, default=10)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument(
        "--oracle-path",
        type=Path,
        default=DEFAULT_ORACLE_PATH,
    )
    args = parser.parse_args()

    check_bootstrap_workspace(args.mode, args.workspace_id)

    if not args.oracle_path.exists():
        raise SystemExit(f"oracle 파일이 없다: {args.oracle_path}")

    questions = load_oracle(args.oracle_path)
    subset = select_subset(questions, per_type=args.per_type)

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    normalizer = LongMemEvalSessionNormalizer()
    summary: dict[str, int] = {}

    try:
        if args.mode == "eval":
            if not subset:
                raise SystemExit("수집할 문항이 없다.")
            assignments = assign_workspaces(subset, base=args.workspace_base)
            with session_factory() as db_session:
                for assignment in assignments:
                    ensure_workspace(
                        db_session,
                        workspace_id=assignment.workspace_id,
                        name=assignment.workspace_name,
                    )
            write_manifest(args.manifest_out, assignments)

            total_sessions = 0
            for assignment, question in zip(
                assignments, subset, strict=True
            ):
                print(
                    f"[{assignment.question_id}] "
                    f"ws={assignment.workspace_id} "
                    f"세션 {len(question.sessions)}건"
                )
                for session in question.sessions:
                    _ingest_one(
                        session,
                        workspace_id=assignment.workspace_id,
                        normalizer=normalizer,
                        session_factory=session_factory,
                        summary=summary,
                        prefix=f"{assignment.workspace_id} ",
                    )
                    total_sessions += 1

            created = summary.get("created/created", 0)
            print("\n=== 수집 결과 (mode=eval, 문항별 격리) ===")
            print(f"  문항: {len(assignments)}")
            print(
                f"  workspace: {assignments[0].workspace_id}"
                f"~{assignments[-1].workspace_id}"
            )
            print(f"  적재 시도: {total_sessions}")
            print(f"  신규 수집: {created}")
            print(f"  스킵(재사용): {total_sessions - created}")
            print(f"  manifest: {args.manifest_out}")
        else:
            sessions = bootstrap_sessions(
                questions, subset, limit=args.limit
            )
            if not sessions:
                raise SystemExit("수집할 세션이 없다.")
            for session in sessions:
                _ingest_one(
                    session,
                    workspace_id=args.workspace_id,
                    normalizer=normalizer,
                    session_factory=session_factory,
                    summary=summary,
                )
            created = summary.get("created/created", 0)
            print(
                f"\n=== 수집 결과 "
                f"(mode=bootstrap, ws={args.workspace_id}) ==="
            )
            print(f"  대상 세션: {len(sessions)}")
            print(f"  신규 수집: {created}")
            print(f"  스킵(재사용): {len(sessions) - created}")

        for label, count in sorted(summary.items()):
            print(f"    {label}: {count}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
