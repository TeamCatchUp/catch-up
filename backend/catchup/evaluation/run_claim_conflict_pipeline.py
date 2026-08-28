"""저장된 claim 후보에서 값이 어긋나는 쌍을 찾아 proposal로 남긴다.

`run_resolution_pipeline.py`의 다음 단계다. 저쪽이 같은 대상인지를
정한다면, 이 스크립트는 그렇게 정해진 대상에 붙은 주장끼리 값이
어긋나는지 본다. 대상 판정이 먼저 끝나야 하는 이유는, 이름만 같은 둘을
묶으면 검토 큐가 거짓 모순으로 차기 때문이다.

비교 기준은 어휘 사전이다. 사전이 값의 종류를 정해준 predicate만
견주므로, 스냅샷이 없으면 아무것도 비교하지 못한다. 그럴 때는 판정을
돌리는 대신 무엇을 먼저 해야 하는지 알리고 끝낸다.

여러 번 돌려도 안전하다. 구성이 그대로면 기존 proposal을 그냥 둔다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_claim_conflict_pipeline
    uv run python -m catchup.evaluation.run_claim_conflict_pipeline \
        --workspace-id 1 --ontology-version v2
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    resolve_claim_conflicts,
)


def _load_vocabulary(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    version: str,
) -> ExtractionVocabulary | None:
    """비교 기준이 될 어휘 스냅샷을 읽는다."""
    with uow:
        return uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--ontology-version",
        default=None,
        help="비교 기준 어휘 버전. 생략하면 최신 발행본을 고른다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(session_factory)

    version = args.ontology_version
    if version is None:
        with uow:
            version = resolve_latest_published_version(
                uow.ontology.list_versions(
                    workspace_id=args.workspace_id,
                    ontology_id=CONTRACT_ID,
                )
            )
    if version is None:
        print(
            "발행된 어휘 스냅샷이 없다. "
            "run_vocabulary_convergence_pipeline을 먼저 돌린다."
        )
        engine.dispose()
        return

    vocabulary = _load_vocabulary(
        uow,
        workspace_id=args.workspace_id,
        version=version,
    )
    if vocabulary is None:
        print(
            f"어휘 스냅샷 {version}이 없다. "
            f"run_vocabulary_convergence_pipeline을 먼저 돌린다."
        )
        engine.dispose()
        return
    if not vocabulary.predicate_entries:
        # 이름 목록만 있는 스냅샷은 치역을 모른다. 비교 대상이 하나도
        # 남지 않으므로 돌려도 0건이 나온다. 그 사실을 미리 알린다.
        print(
            f"어휘 스냅샷 {version}에 predicate 사전 항목이 "
            f"없다. 치역을 담은 사전을 먼저 발행한다."
        )
        engine.dispose()
        return

    print(
        f"어휘 스냅샷 {vocabulary.snapshot_id} predicate 사전 "
        f"{len(vocabulary.predicate_entries)}종 주입"
    )

    result = resolve_claim_conflicts(
        workspace_id=args.workspace_id,
        vocabulary=vocabulary,
        uow=uow,
    )

    print("=== Claim 모순 판정 결과 ===")
    print(
        f"  claim 스캔 {result.claims_scanned}"
        f"  | identity 근거 없음 {result.claims_without_subject_key}"
        f" · 비교 대상 아님 {result.claims_not_comparable}"
        f" · 구간 닫힘 {result.claims_closed}"
        f" · 값 해석 실패 {result.claims_unparseable}"
    )
    print(
        f"  비교 그룹 {result.groups_compared}"
        f"  | 모순 그룹 {result.conflicts_found}"
        f" · 날짜 정밀도 겹침 {result.date_precision_overlaps}"
        f"  | 같은 값 중복 관찰(모순 그룹) {result.duplicates_observed}"
    )
    print(
        f"  proposal 생성 {result.proposals_created}"
        f" · 폐기 {result.proposals_abandoned}"
    )

    engine.dispose()


if __name__ == "__main__":
    main()
