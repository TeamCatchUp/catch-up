"""검토 큐를 읽고 결정을 내리는 debug 전용 엔드포인트다.

파이프라인이 만든 안건을 CLI 러너로만 보고 결정하던 것을 HTTP로 연다.
사람이 서는 자리가 셋(문서 발행·병합·모순 판정)이라 큐도 셋으로 나눈다.
하나로 합치면 결정의 payload가 종류마다 달라 한 엔드포인트가 세 모양을
받아야 하는데, 그 통합은 검토 큐 제품 설계가 정해질 때 할 일이다.

불변식은 전부 서비스가 지킨다. 이 라우터는 서비스를 부르고 예외를 상태
코드로 옮기는 껍데기이며, 결정 규칙을 스스로 갖지 않는다. CLI 러너와
같은 함수를 부르므로 그쪽에서 검증된 규칙이 그대로 적용된다.

인증은 붙이지 않는다. `DEBUG_API_ENABLED`이고 ENV가 development일 때만
등록되는 개발 도구이기 때문이다. 대신 결정자를 `debug:test-user`로
못박아, 감사 기록에 남은 결정이 사람의 것이 아님을 나중에도 구분할 수
있게 한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel

from catchup.configs.config import Environment
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
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
    MergeReviewError,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    review_merge_proposal,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])

# 결정자를 고정한다. 개발 도구가 남긴 결정과 사람이 내린 결정이 감사
# 기록에서 구분되지 않으면 저널을 믿을 수 없게 된다.
DEBUG_REVIEWER = "debug:test-user"


class RejectRequest(BaseModel):
    """반려 사유를 담는다. 사유 없는 반려는 서비스가 거부한다."""

    reason: str


class ResolveRequest(BaseModel):
    """모순 판정의 승자를 담는다."""

    winner_claim_id: uuid.UUID


def _guard() -> None:
    """개발 환경 밖에서는 어떤 요청도 받지 않는다."""
    if settings.ENV is not Environment.development:
        raise HTTPException(
            status_code=403,
            detail="development 환경에서만 쓸 수 있다.",
        )


def _uow_factory(workspace_id: int) -> Callable[
    [], KnowledgeMaintenanceUnitOfWork
]:
    """요청마다 새 UnitOfWork를 내는 factory를 만든다.

    Applier가 proposal 단위 transaction을 쓰므로 세션 하나가 아니라
    factory가 필요하다.
    """

    def factory() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            SessionLocal, workspace_id=workspace_id
        )

    return factory


@router.get("/knowledge-review/artifacts")
def list_artifact_proposals(workspace_id: int = 1) -> dict[str, Any]:
    """계류 중인 문서 변경안을 본문 블록과 함께 돌려준다."""
    _guard()
    with _uow_factory(workspace_id)() as uow:
        proposals = uow.artifacts.list_pending_proposals()
    return {
        "items": [
            {
                "id": str(proposal.id),
                "artifact_id": str(proposal.artifact_id),
                "title": proposal.title,
                "status": proposal.status,
                "base_revision_id": (
                    None
                    if proposal.base_revision_id is None
                    else str(proposal.base_revision_id)
                ),
                "blocks": [
                    {
                        "block_kind": block.block_kind,
                        "heading": block.heading,
                        "body": block.body,
                        "claim_ids": [
                            str(claim_id) for claim_id in block.claim_ids
                        ],
                        "proposal_ids": [
                            str(item) for item in block.proposal_ids
                        ],
                        "ontology_version": block.ontology_version,
                    }
                    for block in proposal.blocks
                ],
            }
            for proposal in proposals
        ]
    }


@router.post("/knowledge-review/artifacts/{proposal_id}/approve")
def approve_artifact_proposal(
    proposal_id: uuid.UUID, workspace_id: int = 1
) -> dict[str, Any]:
    """문서 변경안을 승인해 새 판을 발행한다."""
    _guard()
    try:
        result = review_artifact_proposal(
            _uow_factory(workspace_id)(),
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=DEBUG_REVIEWER,
        )
    except ProposalReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "proposal_id": str(result.proposal_id),
        "verdict": result.verdict,
        "revision_id": (
            None if result.revision_id is None else str(result.revision_id)
        ),
        "revision_number": result.revision_number,
        "claims_accepted": result.claims_accepted,
    }


@router.post("/knowledge-review/artifacts/{proposal_id}/reject")
def reject_artifact_proposal(
    proposal_id: uuid.UUID,
    payload: RejectRequest,
    workspace_id: int = 1,
) -> dict[str, Any]:
    """문서 변경안을 사유와 함께 반려한다."""
    _guard()
    try:
        result = review_artifact_proposal(
            _uow_factory(workspace_id)(),
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer=DEBUG_REVIEWER,
            reason=payload.reason,
        )
    except ProposalReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "proposal_id": str(result.proposal_id),
        "verdict": result.verdict,
    }


@router.get("/knowledge-review/merges")
def list_merge_proposals(workspace_id: int = 1) -> dict[str, Any]:
    """계류 중인 병합 안건을 후보 상세와 함께 돌려준다."""
    _guard()
    with _uow_factory(workspace_id)() as uow:
        proposals = uow.mutation_proposals.list_pending_duplicates(
            workspace_id=workspace_id,
        )
    return {
        "items": [
            {
                "id": str(proposal.id),
                "summary": proposal.summary,
                "resolver_metadata": proposal.resolver_metadata,
                "candidates": [
                    {
                        "id": str(candidate.id),
                        "proposed_name": candidate.proposed_name,
                        "proposed_type": candidate.proposed_type,
                        "resolution_status": candidate.resolution_status,
                    }
                    for candidate in proposal.candidates
                ],
            }
            for proposal in proposals
        ]
    }


@router.post("/knowledge-review/merges/{proposal_id}/approve")
def approve_merge_proposal(
    proposal_id: uuid.UUID, workspace_id: int = 1
) -> dict[str, Any]:
    """병합 안건을 승인한다. 적용은 apply 엔드포인트가 맡는다."""
    _guard()
    try:
        result = review_merge_proposal(
            _uow_factory(workspace_id)(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=DEBUG_REVIEWER,
        )
    except MergeReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "proposal_id": str(result.proposal_id),
        "verdict": result.verdict,
    }


@router.post("/knowledge-review/merges/{proposal_id}/reject")
def reject_merge_proposal(
    proposal_id: uuid.UUID,
    payload: RejectRequest,
    workspace_id: int = 1,
) -> dict[str, Any]:
    """병합 안건을 사유와 함께 반려한다."""
    _guard()
    try:
        result = review_merge_proposal(
            _uow_factory(workspace_id)(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer=DEBUG_REVIEWER,
            reason=payload.reason,
        )
    except MergeReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "proposal_id": str(result.proposal_id),
        "verdict": result.verdict,
    }


@router.get("/knowledge-review/contradictions")
def list_contradiction_proposals(workspace_id: int = 1) -> dict[str, Any]:
    """계류 중인 모순 안건을 값 후보와 함께 돌려준다."""
    _guard()
    with _uow_factory(workspace_id)() as uow:
        proposals = uow.mutation_proposals.list_pending_contradictions(
            workspace_id=workspace_id,
        )
    return {
        "items": [
            {
                "id": str(proposal.id),
                "predicate": proposal.predicate,
                "subject_key": proposal.subject_key,
                "summary": proposal.summary,
                "values": [
                    {
                        "claim_id": str(value.claim_id),
                        "value": value.value,
                        "normalized": value.normalized,
                        "statement": value.statement,
                        "observed_at": value.observed_at,
                        "citation_verified": value.citation_verified,
                    }
                    for value in proposal.values
                ],
            }
            for proposal in proposals
        ]
    }


@router.post("/knowledge-review/contradictions/{proposal_id}/resolve")
def resolve_contradiction_proposal(
    proposal_id: uuid.UUID,
    payload: ResolveRequest,
    workspace_id: int = 1,
) -> dict[str, Any]:
    """모순 안건의 승자를 정한다. 적용은 apply 엔드포인트가 맡는다."""
    _guard()
    try:
        result = review_contradiction_proposal(
            _uow_factory(workspace_id)(),
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            winner_claim_id=payload.winner_claim_id,
            reviewer=DEBUG_REVIEWER,
        )
    except ContradictionReviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "proposal_id": str(result.proposal_id),
        "winner_claim_id": str(result.winner_claim_id),
        "loser_claim_ids": [
            str(claim_id) for claim_id in result.loser_claim_ids
        ],
        "valid_to": result.valid_to.isoformat(),
        "valid_to_source": result.valid_to_source,
    }


@router.post("/knowledge-review/apply")
def apply_decisions(workspace_id: int = 1) -> dict[str, Any]:
    """승인된 안건의 결정 저널을 적용한다."""
    _guard()
    result = apply_mutation_proposals(
        _uow_factory(workspace_id), workspace_id=workspace_id
    )
    return {
        "proposals_applied": result.proposals_applied,
        "proposals_failed": result.proposals_failed,
        "candidates_resolved": result.candidates_resolved,
        "candidates_already_resolved": result.candidates_already_resolved,
        "claims_superseded": result.claims_superseded,
        "claims_invalidated": result.claims_invalidated,
        "claims_already_closed": result.claims_already_closed,
    }
