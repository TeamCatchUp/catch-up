"""pending 상태의 병합 안건을 사람이 읽고 승인하거나 반려한다.

정상 경로는 시스템 자동 확정이다. 해소가 병합 계획서를 쓰면 시스템이
그 자리에서 승인하고 적용까지 이어지므로, 이 러너를 거치는 안건은
없다.

이 러너는 kill switch(`KNOWLEDGE_AUTO_MERGE_ENABLED`)를 꺼서 자동
확정을 멈춘 상태에서 쌓인 안건을 손으로 결정해 보는 개발 도구다.
안건은 그래프 언어(노드·merge)가 아니라 도메인 언어로 보여 준다.
결정은 사실("SSO와 SSO 로그인이 같은 기능인가")에 대한 것이고, 그래프
변경은 답에서 기계가 유도한다.

승인은 결정만 기록하고 적용하지 않는다. 적용은
`run_mutation_apply_pipeline`이 결정 저널을 소비해 수행한다. 승인 직후
바로 적용까지 보고 싶으면 `--apply`를 붙인다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.review_merge_proposals
    uv run python -m catchup.evaluation.review_merge_proposals \
        --approve <proposal-id> --reviewer junsu --apply
    uv run python -m catchup.evaluation.review_merge_proposals \
        --reject <proposal-id> --reason "다른 팀이다"
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
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredMergeProposal
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    VERDICT_APPROVED,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    VERDICT_REJECTED,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    MergeReviewError,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    review_merge_proposal,
)

DEFAULT_REVIEWER = "cli"


def render_merge_card(proposal: StoredMergeProposal) -> str:
    """병합 안건 하나를 도메인 언어 카드로 옮긴다."""
    names = [f"'{candidate.proposed_name}'" for candidate in proposal.candidates]
    question = (
        f"{' 와 '.join(names)} 이(가) 같은 것인가?"
        if len(names) >= 2
        else "병합 대상 후보를 찾을 수 없다"
    )
    lines = [
        f"# {question}",
        f"  proposal {proposal.id}",
        f"  judge 요약: {proposal.summary}",
    ]
    reason = proposal.resolver_metadata.get("reason")
    if reason:
        lines.append(f"  judge 근거: {reason}")
    for candidate in proposal.candidates:
        lines.append(
            f"  - {candidate.proposed_name} ({candidate.proposed_type})"
            f" · 현재 상태 {candidate.resolution_status}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--approve", type=uuid.UUID, default=None)
    parser.add_argument("--reject", type=uuid.UUID, default=None)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="승인 직후 결정 저널을 바로 적용한다.",
    )
    args = parser.parse_args()

    if args.approve is not None and args.reject is not None:
        parser.error("--approve와 --reject는 함께 쓸 수 없다")
    if args.reject is not None and not (args.reason or "").strip():
        parser.error("--reject에는 --reason이 있어야 한다")
    if args.apply and args.approve is None:
        parser.error("--apply는 --approve와 함께 쓴다")

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def uow() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory, workspace_id=args.workspace_id
        )

    if args.approve is None and args.reject is None:
        with uow() as read_uow:
            pending = read_uow.mutation_proposals.list_pending_duplicates(
                workspace_id=args.workspace_id,
            )
        print(f"=== pending 병합 안건 {len(pending)}건 ===")
        for proposal in pending:
            print()
            print(render_merge_card(proposal))
        return 0

    verdict = VERDICT_APPROVED if args.approve else VERDICT_REJECTED
    proposal_id = args.approve or args.reject
    try:
        result = review_merge_proposal(
            uow(),
            workspace_id=args.workspace_id,
            proposal_id=proposal_id,
            verdict=verdict,
            reviewer=args.reviewer,
            reason=args.reason,
        )
    except MergeReviewError as error:
        print(f"결정 거부: {error}")
        return 1

    if result.verdict == VERDICT_APPROVED:
        print(f"승인 완료: {result.proposal_id}")
    else:
        print(f"반려 완료: {result.proposal_id} (사유: {args.reason})")

    if args.apply:
        outcome = apply_mutation_proposals(uow, workspace_id=args.workspace_id)
        print(
            f"적용: 안건 {outcome.proposals_applied}건"
            f" · 실패 {outcome.proposals_failed}건"
            f" · 후보 해소 {outcome.candidates_resolved}건"
            f" · 기해소 스킵 {outcome.candidates_already_resolved}건"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
