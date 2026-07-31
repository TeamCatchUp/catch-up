"""모순 안건에 대한 사람의 판정을 저널로 기록한다.

시스템은 값이 갈렸다는 사실만 알고 어느 쪽이 참인지는 모른다. 그
판정은 사람의 몫이며, 사람이 답하는 것은 "어느 값이 맞나" 하나뿐이다.
패자 목록, 구간을 닫을 시각, 적용 명령은 전부 그 답에서 기계가
유도한다.

닫을 시각은 사실 축에서 고른다. 새 값이 참이 된 순간이 곧 옛 값이
끝난 순간이므로 승자의 valid_from을 쓰고, 그것이 없거나 패자보다
앞서면(구간이 뒤집혀 DB CHECK를 어긴다) 결정 시각으로 물러선다.
어느 쪽을 썼는지는 결정 기록에 남겨 나중에 시간 정보 품질을 잴 수
있게 한다.

보류는 이 서비스를 부르지 않는 것이다. 상태 전이도 기록도 없고, 안건은
계류 목록에 그대로 남아 다음에 다시 보인다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

VALID_TO_FROM_WINNER = "winner_valid_from"
VALID_TO_FROM_DECISION = "decision_time"


class ContradictionReviewError(Exception):
    """모순 판정을 받아들일 수 없음을 알린다.

    안건이 없거나 이미 결정됐거나, 승자가 그 안건의 값 후보가 아니거나,
    판정자가 비어 있는 경우를 모두 이 하나로 알린다. 호출자가 할 일은
    어느 경우든 같다.
    """


class ContradictionReviewUnitOfWork(Protocol):
    """모순 판정이 쓰는 transaction 경계를 정의한다."""

    mutation_proposals: MutationProposalRepository
    knowledge_candidates: KnowledgeCandidateRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ContradictionReviewResult:
    """모순 판정 한 번의 결과를 표현한다.

    Attributes:
        proposal_id: 판정한 안건을 가리킨다.
        winner_claim_id: 참으로 정해진 주장을 가리킨다.
        loser_claim_ids: 닫히거나 탈락할 주장들을 가리킨다.
        valid_to: 패자의 구간을 닫을 시각을 나타낸다.
        valid_to_source: 그 시각을 어디서 얻었는지 나타낸다.
    """

    proposal_id: uuid.UUID
    winner_claim_id: uuid.UUID
    loser_claim_ids: tuple[uuid.UUID, ...]
    valid_to: datetime
    valid_to_source: str


def review_contradiction_proposal(
    uow: ContradictionReviewUnitOfWork,
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
    winner_claim_id: uuid.UUID,
    reviewer: str,
    now: datetime | None = None,
) -> ContradictionReviewResult:
    """모순 안건 하나에 승자를 정하고 적용 명령을 남긴다.

    Raises:
        ContradictionReviewError: 판정을 받아들일 수 없을 때 던진다.
    """
    if not reviewer.strip():
        raise ContradictionReviewError("판정자가 비어 있다")

    decided_at = now or datetime.now(UTC)

    with uow:
        proposal = _find_pending(
            uow, workspace_id=workspace_id, proposal_id=proposal_id
        )
        claim_ids = tuple(value.claim_id for value in proposal.values)
        if winner_claim_id not in claim_ids:
            # 안건 밖의 주장을 승자로 지정하면 결정과 근거가 어긋난다.
            raise ContradictionReviewError(
                f"승자 {winner_claim_id}는 안건 {proposal_id}의 값 후보가"
                " 아니다"
            )
        losers = tuple(
            claim_id for claim_id in claim_ids if claim_id != winner_claim_id
        )
        if not losers:
            raise ContradictionReviewError(
                f"안건 {proposal_id}에 닫을 주장이 없다"
            )

        valid_to, valid_to_source = _resolve_valid_to(
            uow,
            winner_claim_id=winner_claim_id,
            loser_claim_ids=losers,
            decided_at=decided_at,
        )

        decision = {
            "winner_claim_id": str(winner_claim_id),
            "loser_claim_ids": [str(claim_id) for claim_id in losers],
            "valid_to": valid_to.isoformat(),
            "valid_to_source": valid_to_source,
            "reviewer": reviewer,
            "decided_at": decided_at.isoformat(),
        }
        supersede_targets = [
            (
                claim_id,
                {
                    "winner_claim_id": str(winner_claim_id),
                    "valid_to": valid_to.isoformat(),
                },
            )
            for claim_id in losers
        ]
        try:
            uow.mutation_proposals.record_contradiction_decision(
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                decision=decision,
                supersede_targets=supersede_targets,
                reviewer=reviewer,
            )
        except MergeProposalAlreadyDecided as error:
            # 계류 확인은 잠금 없는 읽기라 그 사이에 다른 판정이 결정을
            # 확정했을 수 있다. 저장소의 낙관적 가드가 그것을 잡는다.
            raise ContradictionReviewError(
                f"안건 {proposal_id}를 다른 판정이 먼저 결정했다"
            ) from error
        uow.commit()

    logger.info(
        "contradiction_proposal_resolved",
        workspace_id=workspace_id,
        proposal_id=str(proposal_id),
        predicate=proposal.predicate,
        winner_claim_id=str(winner_claim_id),
        loser_count=len(losers),
        valid_to_source=valid_to_source,
        reviewer=reviewer,
    )
    return ContradictionReviewResult(
        proposal_id=proposal_id,
        winner_claim_id=winner_claim_id,
        loser_claim_ids=losers,
        valid_to=valid_to,
        valid_to_source=valid_to_source,
    )


def _find_pending(
    uow: ContradictionReviewUnitOfWork,
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
) -> StoredContradictionProposal:
    """계류 중인 모순 안건을 찾는다."""
    pending = uow.mutation_proposals.list_pending_contradictions(
        workspace_id=workspace_id,
    )
    for proposal in pending:
        if proposal.id == proposal_id:
            return proposal
    raise ContradictionReviewError(
        f"계류 중인 모순 안건 {proposal_id}를 찾을 수 없다"
    )


def _resolve_valid_to(
    uow: ContradictionReviewUnitOfWork,
    *,
    winner_claim_id: uuid.UUID,
    loser_claim_ids: tuple[uuid.UUID, ...],
    decided_at: datetime,
) -> tuple[datetime, str]:
    """패자의 구간을 닫을 시각과 그 출처를 정한다."""
    winner = uow.knowledge_candidates.get_claim_validity(
        claim_id=winner_claim_id,
    )
    winner_valid_from = None if winner is None else winner[1]
    if winner_valid_from is None:
        return decided_at, VALID_TO_FROM_DECISION

    for claim_id in loser_claim_ids:
        loser = uow.knowledge_candidates.get_claim_validity(
            claim_id=claim_id,
        )
        loser_valid_from = None if loser is None else loser[1]
        if loser_valid_from is None:
            continue
        if winner_valid_from <= loser_valid_from:
            # 승자가 패자보다 앞서면 구간이 뒤집혀 CHECK를 어긴다.
            return decided_at, VALID_TO_FROM_DECISION
    return winner_valid_from, VALID_TO_FROM_WINNER
