"""문서 변경안을 사람이 읽고 승인하거나 반려한다.

`run_artifact_compile_pipeline.py`가 올려 둔 변경안을 검토하는 자리다.
인자가 없으면 계류 중인 변경안을 카드 전체로 펼쳐 보여 주기만 하고,
아무것도 쓰지 않는다. 결정은 `--approve`나 `--reject`를 명시할 때만
일어난다. 읽는 일과 쓰는 일을 나누어야 실수로 승인되는 일이 없다.

카드는 저장된 본문을 그대로 옮긴다. 요약을 다시 쓰거나 값을 골라 주면
검토자가 승인하는 문장과 문서에 실릴 문장이 달라진다. 그래서 heading과
body를 손대지 않고, 열린 질문과 다툼만 눈에 띄게 표시한다.

다툼(contested) 블록은 본문이 "상충하는 값 N개"라는 표지뿐이라 후보를
함께 적는다. 표지만 보면 무엇이 갈렸는지 알 수 없다. 여기서도 고르지는
않는다 — 저장된 순서 그대로 나란히 적을 뿐이다.

통짜 승인은 다툼 블록이 있거나 블록 결정이 이미 적힌 안건을 확정하지
못한다. 서비스가 막고 이 러너는 블록 검수 경로로 가라고 안내한다.

반려는 사유가 있어야 한다. 왜 물렸는지 없는 반려는 다음 컴파일이 같은
카드를 다시 올렸을 때 아무 도움이 되지 않는다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.review_artifact_proposals
    uv run python -m catchup.evaluation.review_artifact_proposals \
        --approve <proposal-id> --reviewer junsu
    uv run python -m catchup.evaluation.review_artifact_proposals \
        --reject <proposal-id> --reason "값이 낡았다"
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
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    CODE_BLOCK_REVIEW_IN_PROGRESS,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    CODE_CONTESTED_REQUIRES_BLOCK_REVIEW,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    VERDICT_APPROVED,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    VERDICT_REJECTED,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    review_artifact_proposal,
)

DEFAULT_REVIEWER = "cli"

# 통짜 승인이 막혔을 때 사람에게 보여 줄 안내다. 막혔다는 사실만 알리면
# 검토자는 다음에 무엇을 할지 알 수 없다.
_BLOCKED_APPROVAL_HINTS: dict[str, str] = {
    CODE_CONTESTED_REQUIRES_BLOCK_REVIEW: (
        "다툼 블록이 있어 통짜 승인으로 확정할 수 없다."
        " 블록별로 결정한 뒤 발행 경로로 끝내라."
    ),
    CODE_BLOCK_REVIEW_IN_PROGRESS: (
        "블록 결정이 이미 적혀 있어 통짜 승인으로 확정할 수 없다."
        " 남은 블록을 마저 결정한 뒤 발행 경로로 끝내라."
    ),
}


def render_proposal_card(proposal: StoredArtifactProposal) -> str:
    """변경안 하나를 마크다운 유사 텍스트 카드로 옮긴다.

    본문을 각색하지 않는다. 저장된 heading과 body를 그대로 적고, 열린
    질문과 다툼 블록에만 표시를 붙여 나머지 서술과 구분한다.

    다툼 블록은 후보를 claim_id와 본문 그대로 뒤에 잇는다. 표지 한 줄만
    보면 무엇이 갈렸는지 읽을 수 없기 때문이다.
    """
    lines = [
        f"# {proposal.title}",
        f"  proposal {proposal.id} · 블록 {len(proposal.blocks)}개"
        f" · 열린 질문 {count_open_questions(proposal)}개",
    ]
    for block in proposal.blocks:
        marker = _block_marker(block.block_kind)
        lines.append("")
        lines.append(f"## {marker}{block.heading}")
        lines.append(block.body)
        for variant in block.variants:
            lines.append(f"  - [{variant.claim_id}] {variant.body}")
    return "\n".join(lines)


def _block_marker(block_kind: str) -> str:
    """블록 종류를 카드에서 눈에 띄게 할 표지로 옮긴다."""
    if block_kind == BLOCK_KIND_OPEN_QUESTION:
        return "⚠ "
    if block_kind == BLOCK_KIND_CONTESTED:
        return "⚔ "
    return ""


def count_open_questions(proposal: StoredArtifactProposal) -> int:
    """카드에 담긴 열린 질문 블록 수를 센다."""
    return sum(
        1 for block in proposal.blocks if block.block_kind == BLOCK_KIND_OPEN_QUESTION
    )


def _list_pending(uow: KnowledgeMaintenanceUnitOfWork) -> None:
    """계류 중인 변경안을 목록과 카드로 함께 보여 준다."""
    with uow:
        pending = uow.artifacts.list_pending_proposals()

    if not pending:
        print("검토를 기다리는 변경안이 없다.")
        return

    print(f"=== 계류 중인 변경안 {len(pending)}건 ===")
    for proposal in pending:
        print(
            f"  {proposal.id}  {proposal.title}"
            f"  | 블록 {len(proposal.blocks)}"
            f" · 열린 질문 {count_open_questions(proposal)}"
        )
    for proposal in pending:
        print()
        print(render_proposal_card(proposal))


def _review(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    proposal_id: uuid.UUID,
    verdict: str,
    reviewer: str,
    reason: str | None,
) -> int:
    """결정 하나를 확정하고 프로세스 종료 코드를 돌려준다.

    통짜 승인이 막히는 두 경우는 안내를 함께 찍는다. 검토자가 다음에
    설 자리가 블록 검수라는 것을 알려 주지 않으면 안건이 갇힌 것처럼
    보인다.
    """
    try:
        result = review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict=verdict,
            reviewer=reviewer,
            reason=reason,
        )
    except ProposalReviewError as error:
        print(f"결정을 확정하지 못했다: {error}")
        hint = _BLOCKED_APPROVAL_HINTS.get(error.code or "")
        if hint is not None:
            print(f"  → {hint}")
        return 1

    if result.verdict == VERDICT_APPROVED:
        print(
            f"승인 완료: {result.proposal_id}"
            f" → 판 {result.revision_number} ({result.revision_id})"
        )
    else:
        print(f"반려 완료: {result.proposal_id} (사유: {reason})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--reviewer",
        default=DEFAULT_REVIEWER,
        help="결정을 남길 검토자 이름을 정한다.",
    )
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument(
        "--approve",
        type=uuid.UUID,
        metavar="PROPOSAL_ID",
        help="변경안을 승인하고 새 판으로 쌓는다.",
    )
    decision.add_argument(
        "--reject",
        type=uuid.UUID,
        metavar="PROPOSAL_ID",
        help="변경안을 사유와 함께 반려한다.",
    )
    parser.add_argument(
        "--reason",
        help="반려 사유를 남긴다. --reject에는 반드시 있어야 한다.",
    )
    args = parser.parse_args()

    # 사유 없는 반려는 서비스도 막지만, 여기서 먼저 막아야 DB에 붙기 전에
    # 사용법을 보여 주고 끝낼 수 있다.
    if args.reject is not None and (args.reason is None or not args.reason.strip()):
        parser.error("--reject는 --reason이 있어야 한다")
    if args.reject is None and args.reason is not None:
        parser.error("--reason은 --reject와 함께 쓴다")

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=args.workspace_id,
    )

    try:
        if args.approve is not None:
            return _review(
                uow,
                proposal_id=args.approve,
                verdict=VERDICT_APPROVED,
                reviewer=args.reviewer,
                reason=None,
            )
        if args.reject is not None:
            return _review(
                uow,
                proposal_id=args.reject,
                verdict=VERDICT_REJECTED,
                reviewer=args.reviewer,
                reason=args.reason,
            )
        _list_pending(uow)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
