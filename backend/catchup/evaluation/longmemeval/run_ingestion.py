"""LongMemEval 세션을 knowledge_maintenance 파이프라인에 밀어 넣는다.

`run_ingestion_pipeline.py`가 ChannelTalk payload로 하는 일을 LongMemEval
세션으로 한다. oracle 파일에서 세션을 골라 `SourceChangeEnvelope`로 감싸고
T1(원문 + Observation + 큐 지시)을 확정한다. 그다음 단계인 추출은
`run_extraction_pipeline.py`가 이어받는다.

모드는 둘이다.

- `eval`: 평가 서브셋(`select_subset`)이 쓰는 세션을 모두 넣는다. 한 세션이
  여러 문항의 haystack에 겹쳐 나오므로 session_id로 중복을 지운다.
- `bootstrap`: 서브셋 밖 세션(`bootstrap_sessions`)만 넣는다. 어휘 튜닝용
  이며 평가 대상과 섞이면 안 되므로 workspace를 반드시 따로 준다.

workspace는 섞이면 되돌리기 어렵다. 그래서 실행자가 `--workspace-id`로
직접 정한다. 기본값 902는 평가용이며, bootstrap은 다른 값을 명시한다.

같은 세션을 다시 넣어도 idempotency key로 재사용되므로 여러 번 돌려도
안전하다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_ingestion \\
        --workspace-id 902 --mode eval --per-type 10
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.dataset import OracleSession
from catchup.evaluation.longmemeval.dataset import bootstrap_sessions
from catchup.evaluation.longmemeval.dataset import load_oracle
from catchup.evaluation.longmemeval.dataset import select_subset
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
    원문이 한 번만 저장되어야 재실행이 안전하다.
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


def _eval_sessions(
    questions: Sequence[OracleQuestion],
    *,
    per_type: int,
) -> list[OracleSession]:
    """평가 서브셋이 쓰는 세션을 중복 없이 모은다.

    문항끼리 haystack 세션을 공유하므로 그대로 모으면 같은 세션이 여러 번
    들어온다. session_id로 한 번만 남기고, 순서는 세션 시각 오름차순으로
    맞춰 시간 축대로 수집되게 한다.
    """
    subset = select_subset(questions, per_type=per_type)
    seen: set[str] = set()
    sessions: list[OracleSession] = []
    for question in subset:
        for session in question.sessions:
            if session.session_id in seen:
                continue
            seen.add(session.session_id)
            sessions.append(session)
    sessions.sort(key=lambda session: session.timestamp)
    return sessions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=902)
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

    if not args.oracle_path.exists():
        raise SystemExit(f"oracle 파일이 없다: {args.oracle_path}")

    questions = load_oracle(args.oracle_path)
    if args.mode == "eval":
        sessions = _eval_sessions(questions, per_type=args.per_type)
    else:
        subset = select_subset(questions, per_type=args.per_type)
        sessions = bootstrap_sessions(questions, subset, limit=args.limit)

    if not sessions:
        raise SystemExit("수집할 세션이 없다.")

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    normalizer = LongMemEvalSessionNormalizer()

    summary: dict[str, int] = {}
    for session in sessions:
        result = ingest_and_normalize(
            session_envelope(session, workspace_id=args.workspace_id),
            normalizer=normalizer,
            uow=KnowledgeMaintenanceUnitOfWork(session_factory),
        )
        label = f"{result.ingestion.value}/{result.normalization.value}"
        summary[label] = summary.get(label, 0) + 1
        print(
            f"  {session.session_id}  {label}  "
            f"observation {str(result.observation_id)[:8]}"
        )

    created = summary.get("created/created", 0)
    print(f"\n=== 수집 결과 (mode={args.mode}, ws={args.workspace_id}) ===")
    print(f"  대상 세션: {len(sessions)}")
    print(f"  신규 수집: {created}")
    print(f"  스킵(재사용): {len(sessions) - created}")
    for label, count in sorted(summary.items()):
        print(f"    {label}: {count}")

    engine.dispose()


if __name__ == "__main__":
    main()
