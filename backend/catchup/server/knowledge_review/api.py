"""위키 검수 루프의 정식 HTTP 엔드포인트를 정의한다.

debug 라우터와 달리 인증과 검토자 권한을 요구하고, 결정 저널의 판정자를
실제 사용자로 남긴다. 사람의 결정이 감사 기록이 되려면 "누가" 자리에
`debug:test-user`가 아닌 사람이 들어와야 하기 때문이다.

큐는 하나다. debug가 문서·병합·모순 셋으로 나눠 두었던 것을 문서 변경안
하나의 목록으로 모으고, 모순은 그 안건의 상세에 딸린 충돌로 보여 준다.
사람이 답하는 것은 결국 "이 문서를 이대로 낼까"이고, 값이 갈린 사실은 그
판단의 재료이기 때문이다. 병합 결정은 이 표면에 없다 — 문서 검토와 다른
화면의 일이라 debug 라우터에 남겨 둔다.

불변식은 전부 서비스가 지킨다. 이 라우터는 컨텍스트를 확정하고 서비스를
부르고 예외를 상태 코드로 옮기는 껍데기이며, 결정 규칙을 스스로 갖지
않는다. 오류 코드는 예외 문자열이 아니라 저장소에서 다시 읽은 상태로
정한다 — 예외 문구를 파싱해 분기하면 문구를 다듬는 순간 계약이 깨지고,
문구를 그대로 내보내면 내부 사정이 새어 나간다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.utils import audit_log
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.services.apply_mutation_proposals import ApplyResult
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.list_review_queue import ReviewQueueItem
from catchup.knowledge_maintenance.services.list_review_queue import list_review_queue
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    PROPOSAL_STATUS_PENDING,
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
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    ContradictionReviewError,
)
from catchup.knowledge_maintenance.services.review_contradiction_proposal import (
    review_contradiction_proposal,
)
from catchup.server.knowledge_review.dependencies import ReviewerContext
from catchup.server.knowledge_review.dependencies import ReviewUowFactory
from catchup.server.knowledge_review.dependencies import get_review_uow_factory
from catchup.server.knowledge_review.dependencies import resolve_reviewer_workspace
from catchup.server.knowledge_review.dependencies import review_error
from catchup.server.knowledge_review.schemas import ApplyResponse
from catchup.server.knowledge_review.schemas import ArtifactRefResponse
from catchup.server.knowledge_review.schemas import BlockResponse
from catchup.server.knowledge_review.schemas import ConflictResponse
from catchup.server.knowledge_review.schemas import ConflictValueResponse
from catchup.server.knowledge_review.schemas import DecisionResponse
from catchup.server.knowledge_review.schemas import ProposalDetailResponse
from catchup.server.knowledge_review.schemas import QueueItemResponse
from catchup.server.knowledge_review.schemas import QueuePageResponse
from catchup.server.knowledge_review.schemas import ReadSetResponse
from catchup.server.knowledge_review.schemas import RejectRequest
from catchup.server.knowledge_review.schemas import ResolveRequest
from catchup.server.knowledge_review.schemas import ResolveResponse

router = APIRouter(
    prefix="/api/v1/knowledge-review",
    tags=["Knowledge Review"],
)

CONTRADICTION_KIND = "contradiction"


@router.get(
    path="/queue",
    response_model=QueuePageResponse,
    description="검토 대기 중인 위키 문서 변경안을 충돌 우선으로 조회한다.",
)
@audit_log(action=KnowledgeReviewAction.LIST)
def list_queue(
    contains_conflict: bool | None = Query(
        None, description="충돌 여부로 거른다. 생략하면 전부 본다."
    ),
    limit: int = Query(50, ge=1, le=200, description="한 쪽에 담을 안건 수"),
    offset: int = Query(0, ge=0, description="건너뛸 안건 수"),
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> QueuePageResponse:
    """검토 큐 한 페이지를 돌려준다."""
    page = list_review_queue(
        uow_factory(),
        workspace_id=context.workspace_id,
        contains_conflict=contains_conflict,
        limit=limit,
        offset=offset,
    )
    return QueuePageResponse(
        items=[_to_queue_item(item) for item in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.get(
    path="/queue/{proposal_id}",
    response_model=ProposalDetailResponse,
    description="변경안 본문·근거 장부와 이 대상에 걸린 충돌을 조회한다.",
)
@audit_log(action=KnowledgeReviewAction.DETAIL)
def get_queue_item(
    proposal_id: uuid.UUID,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> ProposalDetailResponse:
    """변경안 하나를 충돌 목록과 함께 돌려준다.

    Raises:
        HTTPException: 이 workspace에 그 변경안이 없을 때 404를 던진다.
    """
    with uow_factory() as uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
        if proposal is None:
            # 저장소가 workspace로 좁혀 읽으므로, 남의 workspace 변경안도
            # 여기서 404가 된다 — 존재 여부를 떠볼 자리가 없다.
            raise review_error(
                404,
                code="PROPOSAL_NOT_FOUND",
                message="변경안을 찾을 수 없습니다.",
            )
        contested = uow.mutation_proposals.find_contested_subject_node_ids(
            workspace_id=context.workspace_id,
        )
        subject_pending = uow.mutation_proposals.find_pending_for_subject_node(
            workspace_id=context.workspace_id,
            node_id=proposal.subject_node_id,
        )
        contradictions = uow.mutation_proposals.list_pending_contradictions(
            workspace_id=context.workspace_id,
        )

    subject_proposal_ids = {
        pending.id
        for pending in subject_pending
        if pending.proposal_kind == CONTRADICTION_KIND
    }
    conflicts = [
        _to_conflict(item)
        for item in contradictions
        if item.id in subject_proposal_ids
    ]
    return _to_detail(
        proposal,
        contains_conflict=proposal.subject_node_id in contested,
        conflicts=conflicts,
    )


@router.post(
    path="/artifacts/{proposal_id}/approve",
    response_model=DecisionResponse,
    description="문서 변경안을 승인해 새 판을 발행한다.",
)
@audit_log(action=KnowledgeReviewAction.APPROVE)
def approve_artifact(
    proposal_id: uuid.UUID,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> DecisionResponse:
    """승인을 확정하고 그 결과를 돌려준다.

    Raises:
        HTTPException: 변경안이 없으면 404, 결정을 받아들일 수 없으면
            409를 던진다.
    """
    try:
        result = review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict=VERDICT_APPROVED,
            reviewer=context.reviewer,
        )
    except ProposalReviewError as error:
        raise _artifact_review_error(uow_factory, proposal_id) from error
    return DecisionResponse(
        proposal_id=str(result.proposal_id),
        verdict=result.verdict,
        revision_id=(
            None if result.revision_id is None else str(result.revision_id)
        ),
        revision_number=result.revision_number,
        claims_accepted=result.claims_accepted,
    )


@router.post(
    path="/artifacts/{proposal_id}/reject",
    response_model=DecisionResponse,
    description="문서 변경안을 사유와 함께 반려한다.",
)
@audit_log(action=KnowledgeReviewAction.REJECT)
def reject_artifact(
    proposal_id: uuid.UUID,
    payload: RejectRequest,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> DecisionResponse:
    """반려를 확정하고 그 결과를 돌려준다.

    사유 없는 반려는 서비스에 닿기 전에 막는다. 서비스와 DB도 같은 것을
    막지만, 그때는 "받아들일 수 없는 결정"과 구별되지 않는 409가 되어
    소비자가 입력을 고치면 되는 상황임을 알 수 없다.

    Raises:
        HTTPException: 사유가 비면 400, 변경안이 없으면 404, 결정을
            받아들일 수 없으면 409를 던진다.
    """
    if not payload.reason.strip():
        raise review_error(
            400,
            code="REASON_REQUIRED",
            message="반려는 사유가 있어야 합니다.",
        )
    try:
        result = review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict=VERDICT_REJECTED,
            reviewer=context.reviewer,
            reason=payload.reason,
        )
    except ProposalReviewError as error:
        raise _artifact_review_error(uow_factory, proposal_id) from error
    return DecisionResponse(
        proposal_id=str(result.proposal_id),
        verdict=result.verdict,
    )


@router.post(
    path="/contradictions/{proposal_id}/resolve",
    response_model=ResolveResponse,
    description="모순 안건의 승자를 정해 결정 저널을 남긴다.",
)
@audit_log(action=KnowledgeReviewAction.RESOLVE)
def resolve_contradiction(
    proposal_id: uuid.UUID,
    payload: ResolveRequest,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> ResolveResponse:
    """모순 판정을 확정하고 그 결과를 돌려준다.

    Raises:
        HTTPException: 판정을 받아들일 수 없으면 409를 던진다.
    """
    try:
        result = review_contradiction_proposal(
            uow_factory(),
            workspace_id=context.workspace_id,
            proposal_id=proposal_id,
            winner_claim_id=payload.winner_claim_id,
            reviewer=context.reviewer,
        )
    except ContradictionReviewError as error:
        raise _contradiction_review_error(
            uow_factory,
            workspace_id=context.workspace_id,
            proposal_id=proposal_id,
            winner_claim_id=payload.winner_claim_id,
        ) from error
    return ResolveResponse(
        proposal_id=str(result.proposal_id),
        winner_claim_id=str(result.winner_claim_id),
        loser_claim_ids=[
            str(claim_id) for claim_id in result.loser_claim_ids
        ],
        valid_to=result.valid_to,
        valid_to_source=result.valid_to_source,
    )


@router.post(
    path="/apply",
    response_model=ApplyResponse,
    description="승인된 안건의 결정 저널을 모두 적용한다.",
)
@audit_log(action=KnowledgeReviewAction.APPLY)
def apply_all(
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> ApplyResponse:
    """workspace의 승인된 안건을 전부 적용한다."""
    result = apply_mutation_proposals(
        uow_factory,
        workspace_id=context.workspace_id,
    )
    return _to_apply_response(result)


@router.post(
    path="/apply/{proposal_id}",
    response_model=ApplyResponse,
    description="승인된 안건 하나의 결정 저널을 적용한다.",
)
@audit_log(action=KnowledgeReviewAction.APPLY)
def apply_one(
    proposal_id: uuid.UUID,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
) -> ApplyResponse:
    """안건 하나만 적용한다.

    적용이 0건이면 404다. 승인 목록에 없는 안건은 아직 결정되지 않았거나
    이미 적용된 것이고, 둘 다 "이 요청으로 적용된 것이 없다"는 사실을
    소비자가 성공으로 읽으면 안 된다. 적용 중 실패한 안건은 0건이 아니라
    proposals_failed로 세지므로 여기에 걸리지 않는다.

    Raises:
        HTTPException: 적용된 안건이 없으면 404를 던진다.
    """
    result = apply_mutation_proposals(
        uow_factory,
        workspace_id=context.workspace_id,
        proposal_id=proposal_id,
    )
    if result.proposals_applied == 0 and result.proposals_failed == 0:
        raise review_error(
            404,
            code="PROPOSAL_NOT_APPLIED",
            message="적용할 승인 안건을 찾을 수 없습니다.",
        )
    return _to_apply_response(result)


def _artifact_review_error(
    uow_factory: ReviewUowFactory,
    proposal_id: uuid.UUID,
) -> HTTPException:
    """문서 변경안 결정 실패를 상태 코드와 오류 코드로 옮긴다.

    서비스의 예외 계층은 `ProposalReviewError` 하나뿐이라 종류를 예외에서
    읽을 수 없다. 그래서 실패한 뒤에 저장소를 한 번 더 읽어 지금 상태로
    코드를 정한다. 읽기 전용이고 결정 규칙을 다시 판정하지 않는다 —
    소비자가 무엇을 고쳐야 하는지 알려 주는 진단일 뿐이다.
    """
    with uow_factory() as uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
        if proposal is None:
            return review_error(
                404,
                code="PROPOSAL_NOT_FOUND",
                message="변경안을 찾을 수 없습니다.",
            )
        if proposal.status != PROPOSAL_STATUS_PENDING:
            return review_error(
                409,
                code="ALREADY_DECIDED",
                message="이미 결정된 변경안입니다.",
            )
        latest = uow.artifacts.find_latest_revision_id_and_number(
            artifact_id=proposal.artifact_id,
        )
    latest_revision_id = None if latest is None else latest[0]
    if latest_revision_id != proposal.base_revision_id:
        return review_error(
            409,
            code="STALE_BASE_REVISION",
            message="문서가 새 판으로 넘어가 이 변경안은 낡았습니다.",
        )
    return review_error(
        409,
        code="PROPOSAL_NOT_REVIEWABLE",
        message="지금 이 변경안에 결정을 확정할 수 없습니다.",
    )


def _contradiction_review_error(
    uow_factory: ReviewUowFactory,
    *,
    workspace_id: int,
    proposal_id: uuid.UUID,
    winner_claim_id: uuid.UUID,
) -> HTTPException:
    """모순 판정 실패를 상태 코드와 오류 코드로 옮긴다.

    계류 목록에 없으면 없는 안건과 이미 결정된 안건이 한 사실로 보인다.
    저장소에 그 둘을 가르는 조회가 없어 하나의 409로 알린다 — 어느
    쪽이든 소비자가 할 일은 큐를 다시 읽는 것으로 같다.
    """
    with uow_factory() as uow:
        pending = uow.mutation_proposals.list_pending_contradictions(
            workspace_id=workspace_id,
        )
    found = next((item for item in pending if item.id == proposal_id), None)
    if found is None:
        return review_error(
            409,
            code="CONTRADICTION_NOT_PENDING",
            message="계류 중인 모순 안건이 아닙니다.",
        )
    if winner_claim_id not in {value.claim_id for value in found.values}:
        return review_error(
            409,
            code="WINNER_NOT_CANDIDATE",
            message="승자로 지정한 주장이 이 안건의 값 후보가 아닙니다.",
        )
    return review_error(
        409,
        code="CONTRADICTION_NOT_RESOLVABLE",
        message="지금 이 모순 안건을 판정할 수 없습니다.",
    )


def _to_queue_item(item: ReviewQueueItem) -> QueueItemResponse:
    """큐 한 줄을 응답으로 옮긴다."""
    return QueueItemResponse(
        proposal_id=str(item.proposal_id),
        status=item.status,
        artifact=ArtifactRefResponse(
            id=str(item.artifact_id), title=item.title
        ),
        summary=item.summary,
        origin=item.origin,
        contains_conflict=item.contains_conflict,
        created_at=item.created_at,
    )


def _to_detail(
    proposal: StoredArtifactProposal,
    *,
    contains_conflict: bool,
    conflicts: list[ConflictResponse],
) -> ProposalDetailResponse:
    """변경안 하나를 상세 응답으로 옮긴다."""
    claim_ids: dict[str, None] = {}
    proposal_ids: dict[str, None] = {}
    blocks: list[BlockResponse] = []
    for block in proposal.blocks:
        block_claim_ids = [str(claim_id) for claim_id in block.claim_ids]
        block_proposal_ids = [str(item) for item in block.proposal_ids]
        for claim_id in block_claim_ids:
            claim_ids.setdefault(claim_id, None)
        for item in block_proposal_ids:
            proposal_ids.setdefault(item, None)
        blocks.append(
            BlockResponse(
                block_kind=block.block_kind,
                heading=block.heading,
                body=block.body,
                claim_ids=block_claim_ids,
                proposal_ids=block_proposal_ids,
                ontology_version=block.ontology_version,
            )
        )
    return ProposalDetailResponse(
        proposal_id=str(proposal.id),
        status=proposal.status,
        artifact=ArtifactRefResponse(
            id=str(proposal.artifact_id), title=proposal.title
        ),
        origin=proposal.origin,
        created_at=proposal.created_at,
        base_revision_id=(
            None
            if proposal.base_revision_id is None
            else str(proposal.base_revision_id)
        ),
        contains_conflict=contains_conflict,
        blocks=blocks,
        read_set=ReadSetResponse(
            claim_ids=list(claim_ids),
            proposal_ids=list(proposal_ids),
        ),
        conflicts=conflicts,
    )


def _to_conflict(
    proposal: StoredContradictionProposal,
) -> ConflictResponse:
    """모순 안건 하나를 상세의 충돌 항목으로 옮긴다."""
    return ConflictResponse(
        proposal_id=str(proposal.id),
        predicate=proposal.predicate,
        summary=proposal.summary,
        values=[
            ConflictValueResponse(
                claim_id=str(value.claim_id),
                value=value.value,
                statement=value.statement,
            )
            for value in proposal.values
        ],
    )


def _to_apply_response(result: ApplyResult) -> ApplyResponse:
    """적용 집계를 응답으로 옮긴다."""
    return ApplyResponse(
        proposals_applied=result.proposals_applied,
        proposals_failed=result.proposals_failed,
        candidates_resolved=result.candidates_resolved,
        candidates_already_resolved=result.candidates_already_resolved,
        claims_superseded=result.claims_superseded,
        claims_invalidated=result.claims_invalidated,
        claims_already_closed=result.claims_already_closed,
    )
