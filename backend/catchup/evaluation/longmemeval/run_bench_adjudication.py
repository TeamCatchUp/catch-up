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

건별 실패는 그 자리에서 멈추지 않고 끝까지 시도한 뒤 모아서 보고한다.
한 건이라도 남으면 exit 1이다. 경고만 남기고 0으로 끝내면 오케스트레이터가
지식이 빠진 workspace를 완료로 기록한다.

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
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationCounts
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationSteps
from catchup.evaluation.longmemeval.bench_adjudication import StepOutcome
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
) -> StepOutcome:
    """계류 중인 병합 안건을 전부 승인한다.

    벤치마크에서 병합 안건은 judge가 이미 같은 대상이라고 판정한
    것뿐이다. 사람의 자리는 그 판정을 확정하는 일이므로 전부 승인한다.

    실패한 안건은 세어 돌려준다. 경고만 남기고 0으로 끝내면 병합되지
    않은 후보가 남은 workspace가 완료로 기록된다.
    """
    with uow:
        pending = uow.mutation_proposals.list_pending_duplicates(
            workspace_id=workspace_id,
        )

    approved = 0
    failed = 0
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
            failed += 1
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
    return StepOutcome(done=approved, failed=failed)


def _apply_mutations(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    workspace_id: int,
) -> StepOutcome:
    """결정 저널을 적용한다. 승인·판정이 만든 명령만 소비한다."""
    result = apply_mutation_proposals(uow_factory, workspace_id=workspace_id)
    if result.proposals_failed:
        logger.warning(
            "bench_adjudication_apply_failed",
            failed=result.proposals_failed,
        )
    return StepOutcome(
        done=result.proposals_applied,
        failed=result.proposals_failed,
    )


def _detect_conflicts(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
) -> StepOutcome:
    """값이 어긋나는 주장 쌍을 찾아 안건으로 남긴다."""
    result = resolve_claim_conflicts(
        workspace_id=workspace_id,
        vocabulary=vocabulary,
        uow=uow,
    )
    return StepOutcome(done=result.conflicts_found)


def _adjudicate_contradictions(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> StepOutcome:
    """계류 중인 모순 안건을 recency 규칙으로 판정한다.

    판정하지 못한 안건은 세어 돌려준다. 그 안건이 계류로 남으면 진 값이
    살아 있는 채로 카드가 컴파일된다.
    """
    with uow:
        pending = uow.mutation_proposals.list_pending_contradictions(
            workspace_id=workspace_id,
        )

    decided = 0
    failed = 0
    for proposal in pending:
        candidates = [candidate_from_value(v) for v in proposal.values]
        if not candidates:
            logger.warning(
                "bench_adjudication_skipped",
                proposal_id=str(proposal.id),
                kind="contradiction",
                reason="값 후보가 없다",
            )
            failed += 1
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
            failed += 1
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
    return StepOutcome(done=decided, failed=failed)


def _compile_artifacts(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    vocabulary: ExtractionVocabulary,
    limit: int,
) -> StepOutcome:
    """모든 entity의 카드를 컴파일해 변경안으로 올린다.

    멱등 키가 이미 결정된 변경안과 부딪힌 노드는 컴파일러가 건너뛰고
    충돌로 센다. 그 entity의 새 카드는 만들어지지 않으므로 실패로 올려
    보낸다 — 로그에만 남기면 exit 0으로 끝나 오케스트레이터가 카드 빠진
    workspace를 완료로 기록한다.
    """
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
    return StepOutcome(
        done=result.proposals_created + result.proposals_revived,
        failed=result.proposals_conflicted,
    )


def _approve_artifacts(uow: KnowledgeMaintenanceUnitOfWork) -> StepOutcome:
    """계류 중인 문서 변경안을 전부 승인해 판으로 확정한다.

    실패한 변경안은 세어 돌려준다. 승인되지 않은 카드는 조회에 잡히지
    않으므로 그만큼 답이 비어 나온다.
    """
    with uow:
        pending = uow.artifacts.list_pending_proposals()

    approved = 0
    failed = 0
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
            failed += 1
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
    return StepOutcome(done=approved, failed=failed)


def report_counts(counts: AdjudicationCounts) -> int:
    """한 회차 결과를 찍고 종료 코드를 정한다.

    처리하지 못한 안건이 하나라도 있으면 1이다. 건별 실패를 경고로만
    남기고 0으로 끝내면 오케스트레이터는 exit code만 보므로 지식이 빠진
    workspace를 완료로 기록하고 다음 문항으로 넘어간다.
    """
    print("=== 무인 판정 결과 ===")
    print(f"  ① 병합 자동 승인 {counts.merges_approved}")
    print(f"  ② 병합 적용 {counts.merges_applied}")
    print(f"  ③ 모순 감지 {counts.conflicts_found}")
    print(f"  ④ 모순 판정(recency) {counts.contradictions_decided}")
    print(f"  ⑤ 판정 적용 {counts.supersedes_applied}")
    print(f"  ⑥ 카드 컴파일 {counts.artifacts_compiled}")
    print(f"  ⑦ 카드 자동 승인 {counts.artifacts_approved}")
    if not counts.failures:
        return 0

    # 여기까지 왔다는 것은 전 건을 시도했다는 뜻이다. 첫 실패에서 멈추지
    # 않는 대신, 남은 안건이 있으면 실패로 끝낸다.
    print("=== 처리하지 못한 안건 ===")
    print(f"  병합 승인 실패 {counts.merges_failed}")
    print(f"  적용 실패 {counts.mutations_failed}")
    print(f"  모순 판정 실패 {counts.contradictions_failed}")
    print(f"  카드 컴파일 충돌 {counts.compilations_failed}")
    print(f"  카드 승인 실패 {counts.artifacts_failed}")
    print(
        f"  합계 {counts.failures}건이 계류로 남았다. "
        "그만큼 지식이 빠진 채로 점수가 나오므로 실패로 끝낸다. "
        "bench_adjudication_skipped·bench_adjudication_apply_failed 로그에서 "
        "사유를 확인한다."
    )
    return 1


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

    return report_counts(counts)


if __name__ == "__main__":
    raise SystemExit(main())
