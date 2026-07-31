"""사람이 내린 문서 변경안 결정을 한 transaction으로 확정한다.

승인은 두 가지 쓰기를 함께 해야 한다. 변경안을 승인으로 끝맺는 일과 그
내용을 새 판으로 쌓는 일이다. 둘이 나뉘면 승인은 됐는데 문서에 실리지
않은 상태나, 판은 생겼는데 어느 승인에서 나왔는지 모르는 상태가 남는다.
그래서 이 서비스는 두 쓰기를 하나의 transaction 안에서만 한다.

승인 전에 딛고 선 판이 아직 최신인지 본다. 검토자가 화면을 보던 사이에
다른 승인이 새 판을 쌓았다면, 그 변경안은 지금 문서가 아닌 지나간 문서를
고치는 것이다. 그대로 얹으면 사이에 끼어든 승인이 조용히 지워진다.

결정이 끝난 변경안은 다시 판정하지 않고 예외로 알린다. 무동작으로 넘기면
호출자는 자기 결정이 반영된 줄 알지만 실제로는 아무 일도 없었던 것이 된다.
사람의 결정을 다루는 자리라 침묵이 가장 위험하다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from typing import Self

from sqlalchemy.exc import IntegrityError

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

VERDICT_APPROVED = "approved"
VERDICT_REJECTED = "rejected"

_VERDICTS = (VERDICT_APPROVED, VERDICT_REJECTED)

PROPOSAL_STATUS_PENDING = "pending"


class ProposalReviewError(Exception):
    """검토 결정을 받아들일 수 없음을 알린다.

    변경안이 없거나 이미 결정됐거나, 딛고 선 판이 낡았거나, 반려에 사유가
    없는 경우를 모두 이 하나로 알린다. 호출자가 할 일은 어느 경우든 같다.
    결정을 거절하고 사람에게 지금 상태를 다시 보여 주는 것이다.

    동시 승인이 판 번호에서 부딪혀 저장소가 IntegrityError를 던지는 것도
    여기에 포함한다. 그것도 결국 "이 결정은 지금 확정할 수 없다"는 같은
    말이므로, 호출자가 저장 계층 예외까지 따로 잡게 두지 않는다.

    두 검토가 같은 변경안을 두고 부딪혀 저장소가 ProposalAlreadyDecided를
    던지는 것도 마찬가지다.
    """


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """검토 한 번의 결과를 표현한다.

    Attributes:
        proposal_id: 판정한 변경안을 가리킨다.
        verdict: 내려진 결정을 나타낸다.
        revision_id: 승인이 만든 판을 가리킨다. 반려면 없다.
        revision_number: 승인이 만든 판의 번호를 나타낸다. 반려면 없다.
        claims_accepted: 승인이 새로 확정한 claim 수를 나타낸다.
            반려면 0이다.
    """

    proposal_id: uuid.UUID
    verdict: str
    revision_id: uuid.UUID | None
    revision_number: int | None
    claims_accepted: int = 0


class ArtifactReviewUnitOfWork(Protocol):
    """검토 확정이 쓰는 transaction 경계를 정의한다.

    mutation proposal 저장소는 여기에 없다. 문서 승인은 claim_section의
    claim 확정만 함축하고, open_question에 실린 계류 안건에는 어떤
    결정도 함축하지 않는다 — 접근 자체가 없어야 그 불변식이 구조로
    보장된다.
    """

    artifacts: ArtifactRepository
    knowledge_candidates: KnowledgeCandidateRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


def review_artifact_proposal(
    uow: ArtifactReviewUnitOfWork,
    *,
    proposal_id: uuid.UUID,
    verdict: str,
    reviewer: str,
    reason: str | None = None,
) -> ReviewResult:
    """변경안 하나에 사람의 결정을 확정하고 결과를 돌려준다.

    승인이면 내용을 새 판으로 쌓고 그 판의 식별자와 번호를 돌려준다.
    반려면 사유를 남기고 판은 만들지 않는다.

    Raises:
        ProposalReviewError: 결정을 받아들일 수 없을 때 던진다.
    """
    if verdict not in _VERDICTS:
        raise ProposalReviewError(f"알 수 없는 verdict {verdict!r}")
    if not reviewer.strip():
        # 누가 결정했는지 없는 승인은 감사 기록이 되지 못한다.
        raise ProposalReviewError("검토자가 비어 있다")

    with uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
        if proposal is None:
            raise ProposalReviewError(f"변경안 {proposal_id}를 찾을 수 없다")
        if proposal.status != PROPOSAL_STATUS_PENDING:
            raise ProposalReviewError(
                f"변경안 {proposal_id}는 이미 {proposal.status} 상태다"
            )

        if verdict == VERDICT_REJECTED:
            if reason is None or not reason.strip():
                raise ProposalReviewError("반려는 사유가 있어야 한다")
            try:
                uow.artifacts.mark_rejected(
                    proposal_id=proposal_id,
                    reviewer=reviewer,
                    reason=reason,
                )
                uow.commit()
            except ProposalAlreadyDecided as error:
                # 위의 계류 검사는 잠금 없는 읽기라, 그 사이에 다른 검토가
                # 결정을 확정했을 수 있다. 저장소가 그것을 잡아 주므로
                # 이 서비스의 거부 하나로 옮겨 담는다.
                raise ProposalReviewError(
                    f"변경안 {proposal_id}를 다른 검토가 먼저 결정했다"
                ) from error
            logger.info(
                "artifact_proposal_rejected",
                proposal_id=str(proposal_id),
                artifact_id=str(proposal.artifact_id),
                reviewer=reviewer,
            )
            return ReviewResult(
                proposal_id=proposal_id,
                verdict=VERDICT_REJECTED,
                revision_id=None,
                revision_number=None,
            )

        latest = uow.artifacts.find_latest_revision_id_and_number(
            artifact_id=proposal.artifact_id,
        )
        latest_revision_id = None if latest is None else latest[0]
        if latest_revision_id != proposal.base_revision_id:
            # 검토 사이에 문서가 다른 판으로 넘어갔다. 지금 얹으면 그
            # 사이의 승인이 지워지므로, 다시 만들어 올리게 돌려보낸다.
            raise ProposalReviewError(
                f"변경안 {proposal_id}가 딛고 선 판이 최신이 아니다"
            )
        revision_number = 1 if latest is None else latest[1] + 1

        try:
            revision_id = uow.artifacts.add_revision(
                artifact_id=proposal.artifact_id,
                revision_number=revision_number,
                blocks=proposal.blocks,
                source_proposal_id=proposal_id,
            )
            uow.artifacts.mark_approved(
                proposal_id=proposal_id,
                reviewer=reviewer,
            )
            # 문서에 근거로 실린 claim은 이 승인으로 canonical 지식이
            # 된다. 판·상태·확정이 한 transaction이어야 셋이 어긋난
            # 상태가 남지 않는다.
            claim_ids = _claim_section_ids(proposal.blocks)
            claims_accepted = 0
            if claim_ids:
                claims_accepted = uow.knowledge_candidates.accept_claims(
                    claim_ids=claim_ids,
                )
            uow.commit()
        except ProposalAlreadyDecided as error:
            # 다른 검토가 먼저 결정을 확정했다. with 블록을 예외로 빠져
            # 나가면 같은 transaction에서 쌓던 판까지 함께 되감기므로,
            # 반려된 변경안을 가리키는 판이 남지 않는다.
            raise ProposalReviewError(
                f"변경안 {proposal_id}를 다른 검토가 먼저 결정했다"
            ) from error
        except IntegrityError as error:
            # 최신 판을 읽은 뒤 쓰기까지 사이에 다른 승인이 같은 번호를
            # 선점하면 UNIQUE가 막는다. 서비스의 낡음 검사로는 이 race를
            # 좁힐 수 없으므로, 마지막 방어인 DB 제약을 이 서비스의 거부
            # 사유로 옮겨 담는다. add_revision의 flush에서도, commit에서도
            # 날 수 있어 둘을 함께 감싼다.
            raise ProposalReviewError(
                f"변경안 {proposal_id}의 판 번호 {revision_number}를"
                " 다른 승인이 선점했다"
            ) from error

    logger.info(
        "artifact_proposal_approved",
        proposal_id=str(proposal_id),
        artifact_id=str(proposal.artifact_id),
        revision_id=str(revision_id),
        revision_number=revision_number,
        reviewer=reviewer,
        claims_accepted=claims_accepted,
    )
    return ReviewResult(
        proposal_id=proposal_id,
        verdict=VERDICT_APPROVED,
        revision_id=revision_id,
        revision_number=revision_number,
        claims_accepted=claims_accepted,
    )


def _claim_section_ids(
    blocks: tuple[ArtifactBlock, ...],
) -> tuple[uuid.UUID, ...]:
    """claim_section 블록의 근거 claim id를 순서 보존으로 모은다.

    open_question의 proposal_ids는 여기서 읽지 않는다. 열린 질문은
    제시이지 결정이 아니다.
    """
    seen: dict[uuid.UUID, None] = {}
    for block in blocks:
        if block.block_kind != BLOCK_KIND_CLAIM_SECTION:
            continue
        for claim_id in block.claim_ids:
            seen.setdefault(claim_id, None)
    return tuple(seen)
