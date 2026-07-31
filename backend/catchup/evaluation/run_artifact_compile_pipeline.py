"""claim이 많은 entity의 요약 카드를 컴파일해 검토 큐에 올린다.

`run_claim_conflict_pipeline.py`의 다음 단계다. 저쪽이 값이 어긋나는
쌍을 안건으로 남긴다면, 이 스크립트는 그렇게 쌓인 claim과 안건을 카드
한 장으로 늘어놓아 사람이 한눈에 보게 만든다.

LLM을 부르지 않는다. 카드 본문은 이미 저장된 것을 정해진 순서로 옮긴
것뿐이므로, 같은 입력이면 같은 본문이 나온다. 그래서 여러 번 돌려도
안전하다. 내용 지문이 그대로면 아무것도 쓰지 않고 넘긴다.

어휘 사전은 여기서 읽어 넘긴다. 어느 판본으로 카드를 만들었는지가
블록에 남아야 하고, 그 판본을 고르는 일은 실행을 시작하는 쪽의
결정이기 때문이다.

컴파일은 카드를 확정하지 않는다. 올라간 것은 전부 계류 중인 변경안이며,
승인은 `review_artifact_proposals.py`가 맡는다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_artifact_compile_pipeline
    uv run python -m catchup.evaluation.run_artifact_compile_pipeline \
        --workspace-id 1 --limit 5
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.review_artifact_proposals import render_proposal_card
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_entity_artifacts,
)

ONTOLOGY_VERSION = "2"
DEFAULT_LIMIT = 2


def _load_vocabulary(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    version: str,
) -> ExtractionVocabulary | None:
    """카드에 판본으로 남길 어휘 스냅샷을 읽는다."""
    with uow:
        return uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )


def _print_pending_cards(uow: KnowledgeMaintenanceUnitOfWork) -> None:
    """지금 검토를 기다리는 카드를 전부 펼쳐 보여 준다.

    컴파일 결과는 어느 변경안이 이번에 올라갔는지를 돌려주지 않는다.
    그래서 이번 실행분만 골라내지 않고 계류 큐 전체를 보여 준다. 지난
    실행이 남긴 것도 아직 사람이 봐야 할 카드라는 점에서는 같다.
    """
    with uow:
        pending = uow.artifacts.list_pending_proposals()

    if not pending:
        print("검토를 기다리는 카드가 없다.")
        return

    print(f"=== 계류 중인 카드 {len(pending)}건 (지난 실행분 포함) ===")
    for proposal in pending:
        print()
        print(render_proposal_card(proposal))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="카드를 만들 대상 노드 수를 claim이 많은 순으로 제한한다.",
    )
    parser.add_argument(
        "--ontology-version",
        default=ONTOLOGY_VERSION,
        help="카드에 판본으로 남길 어휘 스냅샷 버전을 정한다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=args.workspace_id,
    )

    vocabulary = _load_vocabulary(
        uow,
        workspace_id=args.workspace_id,
        version=args.ontology_version,
    )
    if vocabulary is None:
        print(
            f"어휘 스냅샷 v{args.ontology_version}이 없다. "
            f"publish_vocabulary_snapshot을 먼저 돌린다."
        )
        engine.dispose()
        return
    if not vocabulary.predicate_entries:
        # 사전이 비면 카드는 만들어지지만 predicate 순서를 사람이 정한
        # 대로 놓지 못하고 이름순으로 떨어진다. 그 사실을 미리 알린다.
        print(
            f"어휘 스냅샷 v{args.ontology_version}에 predicate 사전 항목이 "
            f"없다. 카드의 절 순서는 이름순으로 떨어진다."
        )
    else:
        print(
            f"어휘 스냅샷 v{vocabulary.snapshot_id} predicate 사전 "
            f"{len(vocabulary.predicate_entries)}종 주입"
        )

    result = compile_entity_artifacts(
        uow,
        workspace_id=args.workspace_id,
        vocabulary=vocabulary,
        limit=args.limit,
    )

    print("=== Entity 카드 컴파일 결과 ===")
    print(f"  대상 노드 {result.nodes_considered}")
    # 서비스 필드 이름과 달리 뜻은 "처음 올림"과 "직전 계류를 대신해
    # 다시 올림"이다. 이름을 그대로 적으면 되살아난 행으로 읽히므로
    # 여기서는 뜻으로 적는다.
    print(
        f"  변경안 신규 {result.proposals_created}"
        f" · 갱신 {result.proposals_revived}"
        f" · 접힘 {result.proposals_abandoned}"
        f" · 내용 그대로 {result.unchanged_skipped}"
    )

    _print_pending_cards(uow)

    engine.dispose()


if __name__ == "__main__":
    main()
