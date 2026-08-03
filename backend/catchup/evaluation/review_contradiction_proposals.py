"""모순 안건을 사람이 읽고 어느 값이 참인지 정한다.

시스템은 값이 갈렸다는 사실만 알고 판정하지 않는다. 이 자리에서 사람이
답하는 것은 "어느 값이 맞나" 하나뿐이고, 진 값의 구간을 언제 닫을지와
적용 명령은 그 답에서 기계가 유도한다.

아무 결정도 하지 않고 나가는 것이 보류다. 안건은 계류 목록에 그대로
남아 다음에 다시 보인다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.review_contradiction_proposals
    uv run python -m catchup.evaluation.review_contradiction_proposals \
        --resolve <proposal-id> --winner <claim-id> --reviewer junsu --apply
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)

DEFAULT_REVIEWER = "cli"


def render_contradiction_card(proposal: StoredContradictionProposal) -> str:
    """모순 안건 하나를 도메인 언어 카드로 옮긴다.

    값과 근거 문장을 각색하지 않는다. 어느 쪽이 옳아 보이게 배치하는
    것도 하지 않는다 — 판정은 사람의 몫이다.
    """
    choices = " 인가 ".join(str(value.value) for value in proposal.values)
    lines = [
        f"# {proposal.predicate}은(는) {choices} 인가?",
        f"  proposal {proposal.id} · 대상 {proposal.subject_key}",
    ]
    for value in proposal.values:
        lines.append("")
        lines.append(f"  값 {value.value}")
        lines.append(f"    claim  {value.claim_id}")
        if value.statement:
            lines.append(f"    근거   {value.statement}")
        if value.observed_at:
            lines.append(f"    관찰   {value.observed_at}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--resolve", type=uuid.UUID, default=None)
    parser.add_argument("--winner", type=uuid.UUID, default=None)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="판정 직후 결정 저널을 바로 적용한다.",
    )
    args = parser.parse_args()

    if args.resolve is not None and args.winner is None:
        parser.error("--resolve에는 --winner가 있어야 한다")
    if args.winner is not None and args.resolve is None:
        parser.error("--winner는 --resolve와 함께 쓴다")
    if args.apply and args.resolve is None:
        parser.error("--apply는 --resolve와 함께 쓴다")

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def uow() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory, workspace_id=args.workspace_id
        )

    if args.resolve is None:
        with uow() as read_uow:
            pending = read_uow.mutation_proposals.list_pending_contradictions(
                workspace_id=args.workspace_id,
            )
        print(f"=== 계류 중인 모순 안건 {len(pending)}건 ===")
        for proposal in pending:
            print()
            print(render_contradiction_card(proposal))
        return 0

    try:
        result = review_contradiction_proposal(
            uow(),
            workspace_id=args.workspace_id,
            proposal_id=args.resolve,
            winner_claim_id=args.winner,
            reviewer=args.reviewer,
        )
    except ContradictionReviewError as error:
        print(f"판정 거부: {error}")
        return 1

    print(
        f"판정 완료: {result.proposal_id}"
        f" · 승자 {result.winner_claim_id}"
        f" · 닫을 주장 {len(result.loser_claim_ids)}건"
        f" · valid_to {result.valid_to.isoformat()}"
        f" ({result.valid_to_source})"
    )

    if args.apply:
        outcome = apply_mutation_proposals(uow, workspace_id=args.workspace_id)
        print(
            f"적용: 안건 {outcome.proposals_applied}건"
            f" · 실패 {outcome.proposals_failed}건"
            f" · 구간 닫힘 {outcome.claims_superseded}건"
            f" · 탈락 {outcome.claims_invalidated}건"
            f" · 이미 닫힘 {outcome.claims_already_closed}건"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
