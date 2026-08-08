"""블록마다 내려진 결정을 모아 문서 한 판으로 발행한다.

1단 검토는 변경안을 통째로 승인하거나 반려했다. 2단은 블록 단위로
결정을 받아 두었다가, 발행에서 그것을 한 벌로 조립한다. 승인된 블록만
판에 오르고 반려된 블록은 빠진다. 사람이 문서의 어떤 부분은 받아들이고
어떤 부분은 되돌려 보낼 수 있어야 하기 때문이다.

다툼(contested) 블록은 여기서 두 가지 일을 한 번에 한다. 판에는 승자
후보를 평범한 claim_section으로 실체화해 싣고, 그와 동시에 그 블록이
가리키던 모순 안건에 같은 승자로 결정을 남긴다. 문서에 실린 값과 지식
원장이 아는 값이 갈리면 안 되므로, 둘은 같은 transaction에서만 함께
움직인다. 패자는 판에 남지 않는다 — 무엇이 갈렸었는지는 결정 저널이
간직한다.

조립 전에 두 겹의 낡음을 본다. 블록마다 결정 당시 본 내용의 지문을
지금 본문과 다시 맞춰 보고(사람이 읽지 않은 문장이 실리는 것을 막는다),
문서 전체로는 딛고 선 판이 아직 최신인지 본다(끼어든 승인이 조용히
지워지는 것을 막는다). 둘 중 하나라도 어긋나면 아무것도 쓰지 않는다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from types import TracebackType
from typing import Protocol
from typing import Self

from sqlalchemy.exc import IntegrityError

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import BlockVerdictRepository
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MutationProposalRepository,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

PROPOSAL_STATUS_PENDING = "pending"

BLOCK_VERDICT_APPROVED = "approved"
BLOCK_VERDICT_REJECTED = "rejected"

PUBLISH_VERDICT_APPROVED = "approved"
PUBLISH_VERDICT_REJECTED = "rejected"

# 거절 사유를 가르는 코드다. 호출자는 이 값으로 응답을 정한다.
CODE_NOT_FOUND = "NOT_FOUND"
CODE_ALREADY_DECIDED = "ALREADY_DECIDED"
CODE_UNDECIDED_BLOCKS = "UNDECIDED_BLOCKS"
CODE_STALE_BASE = "STALE_BASE"
CODE_STALE_BLOCK = "STALE_BLOCK"
CODE_CONFLICT_RACE = "CONFLICT_RACE"
CODE_INVALID = "INVALID"

# 블록 사유를 읽지 못했을 때 대신 쓰는 사유다. 변경안 저널 CHECK가 빈
# 사유를 막으므로 합성 사유의 어느 자리도 비워 둘 수 없다.
_FALLBACK_REJECTION_REASON = "발행할 블록이 남지 않았다"


class PublishError(Exception):
    """발행을 받아들일 수 없음을 알린다. code로 사유를 가른다.

    하나의 예외로 모으되 code를 남기는 이유는, 호출자가 사유마다 다르게
    응대해야 하기 때문이다. 미결정 블록이 남았으면 그 번호를 검토자에게
    돌려줘야 하고, 낡음은 화면을 다시 읽게 해야 하며, 경합은 큐를 다시
    읽게 해야 한다. 문자열 메시지를 뜯어 보게 두지 않으려고 코드를
    필드로 세운다.

    Attributes:
        code: 거절 사유를 나타낸다.
        undecided: 아직 결정이 없는 블록 번호를 나타낸다.
            UNDECIDED_BLOCKS가 아니면 비어 있다.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        undecided: tuple[int, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.undecided = undecided


@dataclass(frozen=True, slots=True)
class PublishResult:
    """발행 한 번의 결과를 표현한다.

    Attributes:
        proposal_id: 발행한 변경안을 가리킨다.
        verdict: 변경안이 끝맺은 상태를 나타낸다. 전 블록 반려면
            rejected다.
        revision_id: 발행이 만든 판을 가리킨다. 전 블록 반려면 없다.
        revision_number: 발행이 만든 판의 번호를 나타낸다.
        blocks_published: 판에 실린 블록 수를 나타낸다.
        blocks_rejected: 반려로 빠진 블록 수를 나타낸다.
        contradictions_resolved: 파생으로 결정한 모순 안건 수를 나타낸다.
        claims_accepted: 이 발행이 새로 확정한 claim 수를 나타낸다.
    """

    proposal_id: uuid.UUID
    verdict: str
    revision_id: uuid.UUID | None
    revision_number: int | None
    blocks_published: int
    blocks_rejected: int
    contradictions_resolved: int
    claims_accepted: int


class ArtifactPublishUnitOfWork(Protocol):
    """Publish 전용 UoW다.

    1단 `ArtifactReviewUnitOfWork`와 달리 mutation_proposals에 접근한다.
    contested verdict는 사람이 블록에서 명시로 내린 모순 결정이므로,
    open_question 무결정 불변식과 다르다. 열린 질문은 여전히 제시일 뿐이고
    발행이 그것을 결정하지 않는다.
    """

    artifacts: ArtifactRepository
    knowledge_candidates: KnowledgeCandidateRepository
    mutation_proposals: MutationProposalRepository
    block_verdicts: BlockVerdictRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


class _JoinedUnitOfWork:
    """바깥 transaction에 얹혀 파생 서비스를 부르는 UoW 대역이다.

    파생 resolve는 자기 안에서 `with`에 들어가고 스스로 commit한다.
    바깥 UoW를 그대로 넘기면 실 구현은 새 session을 열고, 빠져나가며
    rollback·close를 하고, 그 뒤 발행의 commit이 갈 곳을 잃는다. 그래서
    경계만 삼키고 저장소는 그대로 빌려 주는 대역을 끼운다. 파생 결정은
    발행과 같은 한 transaction에 남고, 발행이 뒤에서 실패하면 함께
    되감긴다.
    """

    def __init__(self, outer: ArtifactPublishUnitOfWork) -> None:
        self.mutation_proposals = outer.mutation_proposals
        self.knowledge_candidates = outer.knowledge_candidates

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        """바깥 transaction이 확정할 때까지 commit을 미룬다."""
        return None


@dataclass(frozen=True, slots=True)
class _ContestedApproval:
    """실체화와 파생 결정에 함께 쓰는 다툼 블록 승인 하나를 담는다."""

    contradiction_id: uuid.UUID
    winner_claim_id: uuid.UUID


def publish_artifact_proposal(
    uow: ArtifactPublishUnitOfWork,
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
    base_revision_id: uuid.UUID | None,
    reviewer: str,
    now: datetime | None = None,
) -> PublishResult:
    """블록 결정을 모아 변경안을 확정하고 그 결과를 돌려준다.

    승인된 블록이 하나라도 있으면 그것만으로 새 판을 쌓고 변경안을
    승인으로 끝맺는다. 전 블록이 반려됐으면 판을 만들지 않고 블록 사유를
    합성해 반려로 끝맺는다.

    Raises:
        PublishError: 발행을 받아들일 수 없을 때 던진다. code는
            NOT_FOUND·ALREADY_DECIDED·UNDECIDED_BLOCKS·STALE_BASE·
            STALE_BLOCK·CONFLICT_RACE·INVALID 중 하나다.
    """
    if not reviewer.strip():
        # 누가 발행했는지 없는 확정은 감사 기록이 되지 못한다.
        raise PublishError(CODE_INVALID, "발행자가 비어 있다")
    decided_at = datetime.now(UTC) if now is None else now
    # 파생 결정은 자기 로그를 바깥 commit보다 먼저 남긴다. 뒤에서 발행이
    # 엎어지면 DB는 되감기는데 감사 스트림에는 해소 기록만 남으므로,
    # 무엇이 되감겼는지 같은 스트림에 적어 짝을 맞춘다.
    resolved: list[uuid.UUID] = []

    try:
        return _publish_in_transaction(
            uow,
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            base_revision_id=base_revision_id,
            reviewer=reviewer,
            decided_at=decided_at,
            resolved=resolved,
        )
    except Exception as error:
        code = error.code if isinstance(error, PublishError) else "UNEXPECTED"
        logger.warning(
            "artifact_publish_rolled_back",
            workspace_id=workspace_id,
            proposal_id=str(proposal_id),
            code=code,
            rolled_back_contradiction_ids=[
                str(contradiction_id) for contradiction_id in resolved
            ],
            reviewer=reviewer,
        )
        raise


def _publish_in_transaction(
    uow: ArtifactPublishUnitOfWork,
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
    base_revision_id: uuid.UUID | None,
    reviewer: str,
    decided_at: datetime,
    resolved: list[uuid.UUID],
) -> PublishResult:
    """발행의 한 transaction을 연다.

    되감김 로그를 남기려면 파생 결정이 어디까지 나갔는지 알아야 한다.
    `resolved`는 호출자가 쥔 그릇이며, 예외로 빠져나가도 거기까지의
    진행이 남는다.

    Raises:
        PublishError: 발행을 받아들일 수 없을 때 던진다.
    """
    with uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
        if proposal is None:
            # 저장소가 workspace를 고정하므로, 남의 workspace 변경안도
            # 여기서는 없는 것과 같다.
            raise PublishError(
                CODE_NOT_FOUND, f"변경안 {proposal_id}를 찾을 수 없다"
            )
        if proposal.status != PROPOSAL_STATUS_PENDING:
            # 블록 결정을 적는 서비스의 계류 검사는 잠금 없는 읽기라,
            # 그 사이에 전량 승인이 변경안을 끝맺었을 수 있다. 발행은
            # 자기 transaction에서 그것을 다시 확인한다.
            raise PublishError(
                CODE_ALREADY_DECIDED,
                f"변경안 {proposal_id}는 이미 {proposal.status} 상태다",
            )
        if base_revision_id != proposal.base_revision_id:
            # 클라이언트가 본 기준 판과 변경안의 기준이 다르다. 화면이
            # 가리키던 문서와 지금 확정하려는 문서가 같지 않다는 뜻이다.
            raise PublishError(
                CODE_STALE_BASE,
                f"변경안 {proposal_id}의 기준 판이 요청과 다르다",
            )

        verdicts = _verdicts_by_index(uow, proposal)
        contested, assembled, reasons = _assemble(proposal, verdicts)

        latest = uow.artifacts.find_latest_revision_id_and_number(
            artifact_id=proposal.artifact_id,
        )
        latest_revision_id = None if latest is None else latest[0]
        if latest_revision_id != proposal.base_revision_id:
            # 검토 사이에 문서가 다른 판으로 넘어갔다. 지금 얹으면 그
            # 사이의 승인이 지워지므로, 다시 만들어 올리게 돌려보낸다.
            raise PublishError(
                CODE_STALE_BASE,
                f"변경안 {proposal_id}가 딛고 선 판이 최신이 아니다",
            )
        revision_number = 1 if latest is None else latest[1] + 1

        _resolve_contested(
            uow,
            workspace_id=workspace_id,
            approvals=contested,
            reviewer=reviewer,
            decided_at=decided_at,
            resolved=resolved,
        )

        if not assembled:
            reason = "; ".join(reasons) or _FALLBACK_REJECTION_REASON
            try:
                uow.artifacts.mark_rejected(
                    proposal_id=proposal_id,
                    reviewer=reviewer,
                    reason=reason,
                )
                uow.commit()
            except ProposalAlreadyDecided as error:
                raise PublishError(
                    CODE_ALREADY_DECIDED,
                    f"변경안 {proposal_id}를 다른 검토가 먼저 결정했다",
                ) from error
            logger.info(
                "artifact_proposal_published_as_rejected",
                workspace_id=workspace_id,
                proposal_id=str(proposal_id),
                artifact_id=str(proposal.artifact_id),
                blocks_rejected=len(reasons),
                reviewer=reviewer,
            )
            return PublishResult(
                proposal_id=proposal_id,
                verdict=PUBLISH_VERDICT_REJECTED,
                revision_id=None,
                revision_number=None,
                blocks_published=0,
                blocks_rejected=len(reasons),
                contradictions_resolved=0,
                claims_accepted=0,
            )

        try:
            revision_id = uow.artifacts.add_revision(
                artifact_id=proposal.artifact_id,
                revision_number=revision_number,
                blocks=assembled,
                source_proposal_id=proposal_id,
            )
            uow.artifacts.mark_approved(
                proposal_id=proposal_id,
                reviewer=reviewer,
            )
            # 판에 근거로 실린 claim만 canonical 지식이 된다. 반려된
            # 블록의 claim은 상태가 그대로 남는다.
            claim_ids = _claim_section_ids(assembled)
            claims_accepted = 0
            if claim_ids:
                claims_accepted = uow.knowledge_candidates.accept_claims(
                    claim_ids=claim_ids,
                )
            uow.commit()
        except ProposalAlreadyDecided as error:
            # 다른 검토가 먼저 결정을 확정했다. with 블록을 예외로 빠져
            # 나가면 같은 transaction에서 쌓던 판과 파생 모순 결정까지
            # 함께 되감긴다.
            raise PublishError(
                CODE_ALREADY_DECIDED,
                f"변경안 {proposal_id}를 다른 검토가 먼저 결정했다",
            ) from error
        except IntegrityError as error:
            # 최신 판을 읽은 뒤 쓰기까지 사이에 다른 승인이 같은 번호를
            # 선점하면 UNIQUE가 막는다. 서비스의 낡음 검사로는 이 race를
            # 좁힐 수 없으므로, 마지막 방어인 DB 제약을 이 서비스의 거부
            # 사유로 옮겨 담는다.
            raise PublishError(
                CODE_STALE_BASE,
                f"변경안 {proposal_id}의 판 번호 {revision_number}를"
                " 다른 승인이 선점했다",
            ) from error

    logger.info(
        "artifact_proposal_published",
        workspace_id=workspace_id,
        proposal_id=str(proposal_id),
        artifact_id=str(proposal.artifact_id),
        revision_id=str(revision_id),
        revision_number=revision_number,
        blocks_published=len(assembled),
        blocks_rejected=len(reasons),
        contradictions_resolved=len(contested),
        claims_accepted=claims_accepted,
        reviewer=reviewer,
    )
    return PublishResult(
        proposal_id=proposal_id,
        verdict=PUBLISH_VERDICT_APPROVED,
        revision_id=revision_id,
        revision_number=revision_number,
        blocks_published=len(assembled),
        blocks_rejected=len(reasons),
        contradictions_resolved=len(contested),
        claims_accepted=claims_accepted,
    )


def _verdicts_by_index(
    uow: ArtifactPublishUnitOfWork,
    proposal: StoredArtifactProposal,
) -> dict[int, StoredBlockVerdict]:
    """블록 번호마다 결정을 모으고 빠짐·낡음을 검사한다.

    Raises:
        PublishError: 결정이 빠졌거나(UNDECIDED_BLOCKS) 결정 당시 본
            본문과 지금 본문이 다를 때(STALE_BLOCK) 던진다.
    """
    stored = uow.block_verdicts.list_for_proposal(proposal_id=proposal.id)
    by_index = {verdict.block_index: verdict for verdict in stored}
    undecided = tuple(
        index
        for index in range(len(proposal.blocks))
        if index not in by_index
    )
    if undecided:
        raise PublishError(
            CODE_UNDECIDED_BLOCKS,
            f"변경안 {proposal.id}에 결정이 없는 블록이 있다",
            undecided=undecided,
        )
    for index, block in enumerate(proposal.blocks):
        if by_index[index].block_content_hash != block_content_hash(block):
            # 결정을 적은 뒤 본문이 바뀌었다. 그대로 실으면 사람이 읽지
            # 않은 문장에 사람의 이름이 붙는다.
            raise PublishError(
                CODE_STALE_BLOCK,
                f"블록 {index}의 내용이 결정 시점과 다르다",
            )
    return by_index


def _assemble(
    proposal: StoredArtifactProposal,
    verdicts: dict[int, StoredBlockVerdict],
) -> tuple[
    tuple[_ContestedApproval, ...],
    tuple[ArtifactBlock, ...],
    tuple[str, ...],
]:
    """승인된 블록만으로 판 본문을 짓고 파생 결정거리를 함께 모은다.

    쓰기보다 먼저 전부 계산한다. 다툼 블록의 승자가 후보 밖이면 여기서
    거절되므로, 파생 결정이 하나라도 나가기 전에 멈춘다.

    Raises:
        PublishError: 다툼 블록의 승인이 승자를 가리키지 못할 때
            INVALID로 던진다. 조립본이 근거 계약을 어겨도 같다.
    """
    approvals: list[_ContestedApproval] = []
    blocks: list[ArtifactBlock] = []
    reasons: list[str] = []
    for index, block in enumerate(proposal.blocks):
        verdict = verdicts[index]
        if verdict.verdict != BLOCK_VERDICT_APPROVED:
            # 반려 블록의 chosen_winner_claim_id는 여기서 읽지 않는다.
            # 저널은 무검증으로 그 값을 담을 수 있지만, 반려는 "이 대조를
            # 지금 결정하지 않는다"는 뜻이므로 파생 결정을 만들면 안 된다.
            reason = (verdict.rejection_reason or "").strip()
            reasons.append(reason or _FALLBACK_REJECTION_REASON)
            continue
        if block.block_kind != BLOCK_KIND_CONTESTED:
            blocks.append(block)
            continue
        winner_claim_id = _winner(block, verdict, index)
        blocks.append(_materialize(block, winner_claim_id))
        approvals.append(
            _ContestedApproval(
                contradiction_id=block.proposal_ids[0],
                winner_claim_id=winner_claim_id,
            )
        )
    try:
        validate_blocks(blocks)
    except ValueError as error:
        # 조립은 원 블록을 덜어내고 다툼 블록을 갈아끼운다. 그 결과가
        # 근거 계약을 어기면 문서에 실릴 수 없다.
        raise PublishError(
            CODE_INVALID, f"조립한 본문이 근거 계약을 어겼다: {error}"
        ) from error
    return tuple(approvals), tuple(blocks), tuple(reasons)


def _winner(
    block: ArtifactBlock,
    verdict: StoredBlockVerdict,
    index: int,
) -> uuid.UUID:
    """다툼 블록 승인이 가리키는 승자를 후보 안에서 확인한다.

    저널에 무효한 승자가 남아 있을 수 있다. 결정을 적는 서비스는 반려
    경로에서 승자 값을 검증 없이 담고, 그 뒤 사람이 마음을 바꿔 같은
    블록을 승인으로 덮으면 옛 값이 함께 남을 수 있기 때문이다. 발행은
    그 값을 다시 후보 집합에 맞춰 본다.

    Raises:
        PublishError: 승자가 없거나 후보 밖일 때 INVALID로 던진다.
    """
    chosen = verdict.chosen_winner_claim_id
    if chosen is None:
        raise PublishError(
            CODE_INVALID, f"블록 {index}의 다툼 승인에 승자가 없다"
        )
    if chosen not in {variant.claim_id for variant in block.variants}:
        raise PublishError(
            CODE_INVALID, f"블록 {index}의 승자 {chosen}가 후보에 없다"
        )
    if not block.proposal_ids:
        raise PublishError(
            CODE_INVALID, f"블록 {index}가 모순 안건을 가리키지 못한다"
        )
    return chosen


def _materialize(
    block: ArtifactBlock,
    winner_claim_id: uuid.UUID,
) -> ArtifactBlock:
    """다툼 블록을 승자 후보만 남긴 claim_section으로 바꾼다.

    판에는 정해진 값 하나만 남는다. 무엇이 갈렸었고 누가 무엇을 골랐는지는
    결정 저널과 모순 안건이 간직하므로, 문서가 패자를 함께 나를 이유가
    없다. 모순 안건 참조도 떼어낸다 — 발행이 그 안건을 닫았으므로 더는
    답을 기다리는 자리가 아니다.
    """
    variant = next(
        item for item in block.variants if item.claim_id == winner_claim_id
    )
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=block.heading,
        body=variant.body,
        claim_ids=(winner_claim_id,),
        proposal_ids=(),
        ontology_version=block.ontology_version,
        sources=variant.sources,
    )


def _resolve_contested(
    uow: ArtifactPublishUnitOfWork,
    *,
    workspace_id: int,
    approvals: tuple[_ContestedApproval, ...],
    reviewer: str,
    decided_at: datetime,
    resolved: list[uuid.UUID],
) -> None:
    """다툼 승인마다 모순 안건에 같은 승자로 결정을 남긴다.

    기존 판정 서비스를 그대로 부른다. 결정 저널과 supersede 명령을 만드는
    자리를 둘로 늘리면 두 경로가 어긋날 수 있기 때문이다.

    성공한 안건 id를 `resolved`에 쌓는다. 여러 건 가운데 뒤쪽이 터지면
    앞쪽 결정도 함께 되감기므로, 무엇이 되감겼는지 호출자가 감사 스트림에
    적을 수 있어야 한다.

    Raises:
        PublishError: 안건이 이미 결정됐거나 승자를 받아들일 수 없을 때
            CONFLICT_RACE로 던진다. with 블록을 예외로 빠져나가면 발행이
            여기까지 쌓은 것이 함께 되감긴다.
    """
    joined = _JoinedUnitOfWork(uow)
    for approval in approvals:
        try:
            review_contradiction_proposal(
                joined,
                workspace_id=workspace_id,
                proposal_id=approval.contradiction_id,
                winner_claim_id=approval.winner_claim_id,
                reviewer=reviewer,
                now=decided_at,
            )
            resolved.append(approval.contradiction_id)
        except ContradictionReviewError as error:
            raise PublishError(
                CODE_CONFLICT_RACE,
                f"모순 안건 {approval.contradiction_id}를 지금 결정할 수"
                " 없다",
            ) from error


def _claim_section_ids(
    blocks: tuple[ArtifactBlock, ...],
) -> tuple[uuid.UUID, ...]:
    """claim_section 블록의 근거 claim id를 순서 보존으로 모은다.

    실체화된 다툼 승자도 claim_section이므로 여기에 함께 들어온다. 파생
    모순 결정은 패자를 닫을 명령만 남기고 승자를 확정하지는 않으므로,
    승자를 canonical로 올리는 것은 이 자리의 몫이다.
    """
    seen: dict[uuid.UUID, None] = {}
    for block in blocks:
        if block.block_kind != BLOCK_KIND_CLAIM_SECTION:
            continue
        for claim_id in block.claim_ids:
            seen.setdefault(claim_id, None)
    return tuple(seen)
