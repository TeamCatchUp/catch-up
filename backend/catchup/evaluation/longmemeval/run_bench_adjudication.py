"""LongMemEval 검토 큐를 사람 없이 규칙으로 비운다.

벤치마크는 사람이 안건을 하나씩 판정해 줄 수 없다. 그래서 이 러너가
사람의 자리에 앉아 병합과 문서 변경안은 전부 승인하고, 모순은 "가장
최근 관찰이 참"이라는 규칙 하나로 판정한다.

판정은 사람과 똑같은 정문으로 들어간다 — `review_merge_proposal`,
`review_contradiction_proposal`, `review_artifact_proposal`이다. 상태를
SQL로 직접 바꾸면 결정 저널(누가 언제 정했나)이 비고, 그것을 지키는
DB CHECK를 우회하게 된다. 자동 판정도 감사 대상이라는 뜻에서 판정자
이름을 사람 이름과 구분되게 남긴다.

단계 순서는 `bench_adjudication.run_adjudication`이 고정한다. 병합
적용이 모순 감지보다 앞이라는 것이 핵심이다 — 뒤집으면 아직 하나로
묶이지 않은 후보의 주장이 비교 그룹에서 빠져 모순을 통째로 놓친다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.longmemeval.run_bench_adjudication \\
        --workspace-id 902
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.longmemeval.bench_adjudication import REVIEWER_AUTO_ACCEPT
from catchup.evaluation.longmemeval.bench_adjudication import REVIEWER_RECENCY_RULE
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationSteps
from catchup.evaluation.longmemeval.bench_adjudication import candidate_from_value
from catchup.evaluation.longmemeval.bench_adjudication import run_adjudication
from catchup.evaluation.longmemeval.bench_adjudication import select_winner
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_entity_artifacts,
)
from catchup.knowledge_maintenance.services.resolve_claim_conflicts import (
    resolve_claim_conflicts,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    VERDICT_APPROVED as ARTIFACT_APPROVED,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    review_artifact_proposal,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    VERDICT_APPROVED as MERGE_APPROVED,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    MergeReviewError,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    review_merge_proposal,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

ONTOLOGY_VERSION = "2"
DEFAULT_WORKSPACE_ID = 902
# 컴파일 대상은 전체 entity다. 사람이 읽을 카드를 고르는 자리가 아니라
# 평가가 물을 모든 대상을 문서로 만들어야 하는 자리이기 때문이다.
DEFAULT_COMPILE_LIMIT = 100_000

DECISION_EVENT = "bench_adjudication_decided"
TIE_EXHAUSTED_EVENT = "bench_adjudication_tie_exhausted"


def _load_vocabulary(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    version: str,
) -> ExtractionVocabulary | None:
    """모순 비교와 카드 컴파일이 쓸 어휘 스냅샷을 읽는다."""
    with uow:
        return uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )


def _approve_merges(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> int:
    """계류 중인 병합 안건을 전부 승인한다.

    벤치마크에서 병합 안건은 judge가 이미 같은 대상이라고 판정한
    것뿐이다. 사람의 자리는 그 판정을 확정하는 일이므로 전부 승인한다.
    """
    with uow:
        pending = uow.mutation_proposals.list_pending_duplicates(
            workspace_id=workspace_id,
        )

    approved = 0
    for proposal in pending:
        try:
            review_merge_proposal(
                uow,
                workspace_id=workspace_id,
                proposal_id=proposal.id,
                verdict=MERGE_APPROVED,
                reviewer=REVIEWER_AUTO_ACCEPT,
            )
        except MergeReviewError as error:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="merge",
                reason=str(error),
            )
            continue
        approved += 1
        logger.info(
            DECISION_EVENT,
            proposal_id=str(proposal.id),
            kind="merge",
            winner=None,
            tie_break_used=False,
            reviewer=REVIEWER_AUTO_ACCEPT,
        )
    return approved


def _apply_mutations(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    workspace_id: int,
) -> int:
    """결정 저널을 적용한다. 승인·판정이 만든 명령만 소비한다."""
    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)
    if result.proposals_failed:
        logger.warning(
            "bench_adjudication_apply_failed",
            failed=result.proposals_failed,
        )
    return result.proposals_applied


def _detect_conflicts(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
) -> int:
    """값이 어긋나는 주장 쌍을 찾아 안건으로 남긴다."""
    result = resolve_claim_conflicts(
        workspace_id=workspace_id,
        vocabulary=vocabulary,
        uow=uow,
    )
    return result.conflicts_found


def _adjudicate_contradictions(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> int:
    """계류 중인 모순 안건을 recency 규칙으로 판정한다."""
    with uow:
        pending = uow.mutation_proposals.list_pending_contradictions(
            workspace_id=workspace_id,
        )

    decided = 0
    for proposal in pending:
        candidates = [candidate_from_value(v) for v in proposal.values]
        if not candidates:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="contradiction",
                reason="값 후보가 없다",
            )
            continue
        selection = select_winner(candidates)
        if selection.tie_exhausted:
            # 입력 유래 키를 끝까지 써도 갈리지 않은 후보가 남았다는
            # 뜻이다. 승자 값과 닫히는 구간이 같아 판정은 유효하지만,
            # 재실행 시 어느 claim_id가 뽑히는지는 입력 순서를 탄다.
            logger.warning(
                TIE_EXHAUSTED_EVENT,
                proposal_id=str(proposal.id),
                kind="contradiction",
                winner=str(selection.claim_id),
            )
        try:
            review_contradiction_proposal(
                uow,
                workspace_id=workspace_id,
                proposal_id=proposal.id,
                winner_claim_id=selection.claim_id,
                reviewer=REVIEWER_RECENCY_RULE,
            )
        except ContradictionReviewError as error:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="contradiction",
                reason=str(error),
            )
            continue
        decided += 1
        logger.info(
            DECISION_EVENT,
            proposal_id=str(proposal.id),
            kind="contradiction",
            winner=str(selection.claim_id),
            tie_break_used=selection.tie_break_used,
            reviewer=REVIEWER_RECENCY_RULE,
        )
    return decided


def _compile_artifacts(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    limit: int,
) -> int:
    """모든 entity의 카드를 컴파일해 변경안으로 올린다."""
    result = compile_entity_artifacts(
        uow,
        workspace_id=workspace_id,
        vocabulary=vocabulary,
        limit=limit,
    )
    logger.info(
        "bench_adjudication_compiled",
        nodes_considered=result.nodes_considered,
        created=result.proposals_created,
        revived=result.proposals_revived,
        unchanged=result.unchanged_skipped,
        conflicted=result.proposals_conflicted,
    )
    return result.proposals_created + result.proposals_revived


def _approve_artifacts(uow: KnowledgeMaintenanceUnitOfWork) -> int:
    """계류 중인 문서 변경안을 전부 승인해 판으로 확정한다."""
    with uow:
        pending = uow.artifacts.list_pending_proposals()

    approved = 0
    for proposal in pending:
        try:
            review_artifact_proposal(
                uow,
                proposal_id=proposal.id,
                verdict=ARTIFACT_APPROVED,
                reviewer=REVIEWER_AUTO_ACCEPT,
            )
        except ProposalReviewError as error:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="artifact",
                reason=str(error),
            )
            continue
        approved += 1
        logger.info(
            DECISION_EVENT,
            proposal_id=str(proposal.id),
            kind="artifact",
            winner=None,
            tie_break_used=False,
            reviewer=REVIEWER_AUTO_ACCEPT,
        )
    return approved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=DEFAULT_WORKSPACE_ID,
    )
    parser.add_argument(
        "--ontology-version",
        default=ONTOLOGY_VERSION,
        help="모순 비교와 카드에 쓸 어휘 스냅샷 버전을 정한다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_COMPILE_LIMIT,
        help="카드를 만들 대상 노드 수를 제한한다. 기본은 사실상 전체다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=args.workspace_id,
    )

    def uow_factory() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory,
            workspace_id=args.workspace_id,
        )

    try:
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
            return 1
        if not vocabulary.predicate_entries:
            # 사전에 치역이 없으면 비교 대상이 하나도 남지 않아 모순이
            # 0건으로 떨어진다. 조용히 통과하면 "모순이 없다"로 읽힌다.
            print(
                f"어휘 스냅샷 v{args.ontology_version}에 predicate 사전 "
                f"항목이 없다. 치역을 담은 사전을 먼저 발행한다."
            )
            return 1

        steps = AdjudicationSteps(
            approve_merges=lambda: _approve_merges(
                uow, workspace_id=args.workspace_id
            ),
            apply_mutations=lambda: _apply_mutations(
                uow_factory, workspace_id=args.workspace_id
            ),
            detect_conflicts=lambda: _detect_conflicts(
                uow,
                workspace_id=args.workspace_id,
                vocabulary=vocabulary,
            ),
            adjudicate_contradictions=lambda: _adjudicate_contradictions(
                uow, workspace_id=args.workspace_id
            ),
            compile_artifacts=lambda: _compile_artifacts(
                uow,
                workspace_id=args.workspace_id,
                vocabulary=vocabulary,
                limit=args.limit,
            ),
            approve_artifacts=lambda: _approve_artifacts(uow),
        )

        counts = run_adjudication(steps)
    finally:
        engine.dispose()

    print("=== 무인 판정 결과 ===")
    print(f"  ① 병합 자동 승인 {counts.merges_approved}")
    print(f"  ② 병합 적용 {counts.merges_applied}")
    print(f"  ③ 모순 감지 {counts.conflicts_found}")
    print(f"  ④ 모순 판정(recency) {counts.contradictions_decided}")
    print(f"  ⑤ 판정 적용 {counts.supersedes_applied}")
    print(f"  ⑥ 카드 컴파일 {counts.artifacts_compiled}")
    print(f"  ⑦ 카드 자동 승인 {counts.artifacts_approved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
