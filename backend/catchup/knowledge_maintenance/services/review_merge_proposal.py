"""병합 안건에 대한 사람의 결정을 저널로 기록한다.

judge는 "같아 보인다"고 판정만 하고, 합칠지는 사람이 정한다 — 병합은
불가역이라 시스템이 대신 정하면 안 된다. 이 서비스는 그 결정을 proposal
행에 기록만 하고 적용하지 않는다. 적용은 결정 저널을 소비하는 Applier의
몫이다. 결정(approved)과 적용(applied)을 분리해야 Applier가 중간에
죽어도 결정이 사라지지 않는다.

모든 거부는 `MergeReviewError` 하나로 알린다. 껍데기(CLI·API)가 예외
하나만 잡으면 되게 하기 위해서다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

VERDICT_APPROVED = "approved"
VERDICT_REJECTED = "rejected"


class MergeReviewError(Exception):
    """병합 결정이 거부된 모든 사유를 하나의 형태로 알린다."""


class MergeReviewUnitOfWork(Protocol):
    """병합 결정이 쓰는 transaction 경계를 정의한다."""

    mutation_proposals: MutationProposalRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class MergeReviewResult:
    """병합 결정 한 번의 결과를 표현한다.

    Attributes:
        proposal_id: 결정된 안건을 가리킨다.
        verdict: 어떤 결정이었는지 나타낸다.
    """

    proposal_id: uuid.UUID
    verdict: str


def review_merge_proposal(
    uow: MergeReviewUnitOfWork,
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
    verdict: str,
    reviewer: str,
    reason: str | None = None,
) -> MergeReviewResult:
    """병합 안건 하나를 승인하거나 반려한다.

    pending에서만 결정할 수 있다. 이미 결정된 안건에 대한 재결정은
    침묵 무시가 아니라 명시적 거부다 — 감사 기록은 덮어쓸 수 없다.

    Raises:
        MergeReviewError: verdict가 정의 밖이거나, 반려에 사유가
            없거나, 계류 중인 병합 안건이 아니다.
    """
    if verdict not in (VERDICT_APPROVED, VERDICT_REJECTED):
        raise MergeReviewError(f"알 수 없는 결정이다: {verdict}")
    if not reviewer.strip():
        raise MergeReviewError("결정에는 결정자가 있어야 한다")

    cleaned_reason = (reason or "").strip()
    if verdict == VERDICT_REJECTED and not cleaned_reason:
        raise MergeReviewError("반려에는 사유가 있어야 한다")

    with uow:
        try:
            if verdict == VERDICT_APPROVED:
                uow.mutation_proposals.mark_merge_approved(
                    workspace_id=workspace_id,
                    proposal_id=proposal_id,
                    reviewer=reviewer,
                )
            else:
                uow.mutation_proposals.mark_merge_rejected(
                    workspace_id=workspace_id,
                    proposal_id=proposal_id,
                    reviewer=reviewer,
                    reason=cleaned_reason,
                )
        except MergeProposalAlreadyDecided as error:
            raise MergeReviewError(
                "계류 중인 병합 안건이 아니라 결정할 수 없다: "
                f"{proposal_id}"
            ) from error
        uow.commit()

    logger.info(
        "merge_proposal_reviewed",
        workspace_id=workspace_id,
        proposal_id=str(proposal_id),
        verdict=verdict,
        reviewer=reviewer,
    )
    return MergeReviewResult(proposal_id=proposal_id, verdict=verdict)
