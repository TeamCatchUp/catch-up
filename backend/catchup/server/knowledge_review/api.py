"""위키 검수 루프의 정식 HTTP 엔드포인트를 정의한다.

debug 라우터와 달리 인증과 검토자 권한을 요구하고, 결정 저널의 판정자를
실제 사용자로 남긴다. 사람의 결정이 감사 기록이 되려면 "누가" 자리에
`debug:test-user`가 아닌 사람이 들어와야 하기 때문이다.

큐는 하나다. debug가 문서·병합·모순 셋으로 나눠 두었던 것을 문서 변경안
하나의 목록으로 모으고, 모순은 그 안건의 상세에 딸린 충돌로 보여 준다.
사람이 답하는 것은 결국 "이 문서를 이대로 낼까"이고, 값이 갈린 사실은 그
판단의 재료이기 때문이다. 병합 결정은 이 표면에 없다 — 문서 검토와 다른
화면의 일이라 debug 라우터에 남겨 둔다.

모순 직접 판정(resolve)과 적용(apply)도 이 표면에 없다. 기획 UX에 없는
운영 도구를 인증 표면에 노출하지 않으려는 것이며, 그 경로는 debug 라우터와
`catchup/evaluation/`의 CLI 러너가 담당한다.

인가는 두 겹이다. 의존성이 "이 표면에 설 자격"을 보고, 대상이 정해지는
핸들러가 "이 문서를 결정할 수 있는가"를 다시 본다. 문서마다 담당자가 다르니
자격 하나로는 부족하고, 그렇다고 판정을 서비스로 내리면 CLI·debug 표면까지
같은 인가를 지게 된다.

첫 겹은 열람이든 판정이든 workspace 소속 하나다. 두 번째 겹만 문서마다
갈린다. 담당자가 있으면 담당자 본인이고, 없으면 구성원 누구나다. 목록에는
줄마다 그 판정이 can_review로 실린다.

담당자가 없던 문서를 승인·발행으로 확정하면 확정한 사람을 그 문서의
담당자로 등록한다. 이 부여는 라우터에만 둔다. 서비스로 내리면 CLI 러너와
debug 표면의 결정에도 담당자가 생기는데, 그쪽 판정자는 사람이 아니다.

불변식은 전부 서비스가 지킨다. 이 라우터는 컨텍스트를 확정하고 서비스를
부르고 예외를 상태 코드로 옮기는 껍데기이며, 결정 규칙을 스스로 갖지
않는다. 오류 코드는 예외 문자열이 아니라 저장소에서 다시 읽은 상태로
정한다 — 예외 문구를 파싱해 분기하면 문구를 다듬는 순간 계약이 깨지고,
문구를 그대로 내보내면 내부 사정이 새어 나간다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from sqlalchemy.orm import Session

from catchup.audit.actions import KnowledgeReviewAction
from catchup.audit.metadata import KnowledgeReviewAuditMetadata
from catchup.audit.utils import audit_log
from catchup.db import wiki as wiki_queries
from catchup.db.dependencies import get_db
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.block_diff import BlockChange
from catchup.knowledge_maintenance.domain.block_diff import block_markdown
from catchup.knowledge_maintenance.domain.block_diff import change_reason
from catchup.knowledge_maintenance.domain.block_diff import diff_blocks
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.services.list_review_queue import ReviewQueueItem
from catchup.knowledge_maintenance.services.list_review_queue import list_review_queue
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    CODE_NOT_DOCUMENT_OWNER as PUBLISH_CODE_NOT_DOCUMENT_OWNER,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    PublishError,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    publish_artifact_proposal,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    CODE_NOT_DOCUMENT_OWNER as REVIEW_CODE_NOT_DOCUMENT_OWNER,
)
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
from catchup.knowledge_maintenance.services.review_block_verdict import (
    BlockVerdictError,
)
from catchup.knowledge_maintenance.services.review_block_verdict import (
    upsert_block_verdict,
)
from catchup.server.knowledge_review.dependencies import ReviewerContext
from catchup.server.knowledge_review.dependencies import ReviewUowFactory
from catchup.server.knowledge_review.dependencies import get_member_review_uow_factory
from catchup.server.knowledge_review.dependencies import get_review_uow_factory
from catchup.server.knowledge_review.dependencies import resolve_member_reviewer_context
from catchup.server.knowledge_review.dependencies import resolve_reviewer_workspace
from catchup.server.knowledge_review.schemas import ArtifactRefResponse
from catchup.server.knowledge_review.schemas import BaseBlockResponse
from catchup.server.knowledge_review.schemas import BlockChangeResponse
from catchup.server.knowledge_review.schemas import BlockResponse
from catchup.server.knowledge_review.schemas import BlockSourceResponse
from catchup.server.knowledge_review.schemas import BlockVerdictRequest
from catchup.server.knowledge_review.schemas import BlockVerdictResponse
from catchup.server.knowledge_review.schemas import ConflictResponse
from catchup.server.knowledge_review.schemas import ConflictValueResponse
from catchup.server.knowledge_review.schemas import DecisionResponse
from catchup.server.knowledge_review.schemas import ProposalDetailResponse
from catchup.server.knowledge_review.schemas import PublishRequest
from catchup.server.knowledge_review.schemas import PublishResponse
from catchup.server.knowledge_review.schemas import QueueItemResponse
from catchup.server.knowledge_review.schemas import QueuePageResponse
from catchup.server.knowledge_review.schemas import ReadSetResponse
from catchup.server.knowledge_review.schemas import RejectRequest
from catchup.server.knowledge_review.schemas import VariantResponse
from catchup.server.wiki.dependencies import review_error
from catchup.server.wiki.layout import layout_items
from catchup.server.wiki.owners import owners_by_artifact
from catchup.server.wiki.roles import can_decide_artifact
from catchup.server.wiki.schemas import OwnerResponse

router = APIRouter(
    prefix="/api/v1/knowledge-review",
    tags=["Knowledge Review"],
)

# 블록 결정 거절 사유를 상태 코드와 사람이 읽는 문구로 옮긴다. 서비스가
# 준 코드를 그대로 응답 code로 쓰되, 문구는 여기서 정한다 — 예외 문자열은
# 변경안 식별자와 저장소 사정을 담고 있어 그대로 내보낼 수 없다.
_BLOCK_VERDICT_ERRORS: dict[str, tuple[int, str]] = {
    "PROPOSAL_NOT_FOUND": (404, "변경안을 찾을 수 없습니다."),
    "ALREADY_DECIDED": (409, "이미 결정된 변경안입니다."),
    "STALE_BLOCK": (409, "블록 본문이 바뀌었습니다. 다시 읽어 주세요."),
    "INVALID": (422, "블록 결정 요청이 올바르지 않습니다."),
}

# 통짜 승인이 닿지 못하는 자리를 서비스가 코드로 알린다. 여기는 그 코드를
# 상태 코드와 문구로 옮기기만 한다 — 같은 검사를 라우터가 또 하면 정식
# API·debug·CLI 세 표면의 규칙이 갈라진다.
_ARTIFACT_REVIEW_ERRORS: dict[str, tuple[int, str]] = {
    "CONTESTED_REQUIRES_BLOCK_REVIEW": (
        409,
        "다툼 블록이 있어 블록 검토를 거쳐야 합니다.",
    ),
    "BLOCK_REVIEW_IN_PROGRESS": (
        409,
        "블록 검토가 시작된 변경안은 발행으로 끝내야 합니다.",
    ),
}

_PUBLISH_ERRORS: dict[str, tuple[int, str]] = {
    "PROPOSAL_NOT_FOUND": (404, "변경안을 찾을 수 없습니다."),
    "ALREADY_DECIDED": (409, "이미 결정된 변경안입니다."),
    "UNDECIDED_BLOCKS": (409, "아직 결정하지 않은 블록이 있습니다."),
    "STALE_BASE_REVISION": (
        409,
        "문서가 새 판으로 넘어가 이 변경안은 낡았습니다.",
    ),
    "STALE_BLOCK": (409, "블록 본문이 결정 시점과 달라졌습니다."),
    "CONFLICT_RACE": (409, "모순 안건이 먼저 결정돼 발행할 수 없습니다."),
    "INVALID": (422, "발행 요청이 올바르지 않습니다."),
}

# 알 수 없는 코드를 500으로 흘리지 않는다. 서비스가 사유를 늘렸는데 여기가
# 따라오지 못한 것은 소비자 잘못이 아니지만, 그래도 "지금은 안 된다"는
# 사실은 정확하므로 409로 알리고 코드는 그대로 넘긴다.
_UNMAPPED_ERROR = (409, "지금 이 요청을 확정할 수 없습니다.")


def _require_decidable_proposal(
    uow_factory: ReviewUowFactory,
    db: Session,
    context: ReviewerContext,
    proposal_id: uuid.UUID,
) -> StoredArtifactProposal:
    """변경안을 읽고 이 문서를 결정할 수 있는지 판정한다.

    담당자·채널 조회는 UnitOfWork가 아니라 라우터의 db 세션으로 나간다.
    UoW의 내부 세션을 꺼내 쓰면 저장소 경계가 무너지고, 인가 조회가
    knowledge_maintenance 포트에 얹혀 표면마다 따라다니게 된다.

    없음을 알리는 코드는 모든 라우트가 PROPOSAL_NOT_FOUND 하나다. 같은
    "변경안이 없다"를 라우트마다 다른 이름으로 알리면 소비자가 코드를
    라우트별로 갈라 다뤄야 한다.

    Raises:
        HTTPException: 변경안이 없으면 404, 이 문서의 검수 권한이 없으면
            403 NOT_DOCUMENT_REVIEWER를 던진다.
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
    if not can_decide_artifact(
        context.roles,
        artifact_channel_id=wiki_queries.get_artifact_channel_id(
            db, proposal.artifact_id
        ),
        artifact_id=proposal.artifact_id,
        owner_user_ids=frozenset(
            wiki_queries.list_artifact_owner_ids(db, proposal.artifact_id)
        ),
        user_id=context.user.id,
    ):
        raise review_error(
            403,
            code="NOT_DOCUMENT_REVIEWER",
            message="이 문서의 검수 권한이 없습니다.",
        )
    return proposal


def _document_permission_error() -> HTTPException:
    """서비스가 담당자 규칙으로 막은 결정을 권한 응답으로 옮긴다.

    사전 검사가 내는 것과 같은 403 NOT_DOCUMENT_REVIEWER다. 사전 검사를
    지난 뒤에 담당자가 지정된 경우만 이 자리로 오는데, 소비자가 할 일은 두
    경우가 같으므로 코드를 나누지 않는다.
    """
    return review_error(
        403,
        code="NOT_DOCUMENT_REVIEWER",
        message="이 문서의 검수 권한이 없습니다.",
    )


def _load_proposal_for_view(
    uow_factory: ReviewUowFactory,
    proposal_id: uuid.UUID,
) -> StoredArtifactProposal:
    """열람용으로 변경안을 읽는다. 담당자 게이트를 두지 않는다.

    workspace 소속은 의존성이 이미 봤다. 그 위에 문서별 담당자 게이트를 또
    두면 남이 담당하는 문서는 내용조차 볼 수 없게 되는데, 검토는
    보는 일과 정하는 일이 다르다. 그래서 여기서는 워크스페이스 경계만
    지키고, 정할 수 있는지는 응답의 can_review로 따로 알린다.

    Raises:
        HTTPException: 이 workspace에 변경안이 없으면 404
            PROPOSAL_NOT_FOUND를 던진다.
    """
    with uow_factory() as uow:
        proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
    if proposal is None:
        raise review_error(
            404,
            code="PROPOSAL_NOT_FOUND",
            message="변경안을 찾을 수 없습니다.",
        )
    return proposal


def _queue_artifact_ids(
    db: Session,
    *,
    workspace_id: int,
    channel_id: uuid.UUID | None,
    owner_user_id: int | None,
) -> frozenset[uuid.UUID] | None:
    """채널·담당자 조건을 문서 id 집합 하나로 합친다.

    둘 다 주면 교집합이다. 두 조건은 서로를 좁히는 관계이므로 합집합으로
    보면 "이 채널에서 내가 맡은 문서"를 물었을 때 남의 문서까지 나온다.
    둘 다 없으면 None을 돌려주어 서비스가 거르지 않게 한다. 조건은 있으나
    맞는 문서가 없으면 빈 집합이고, 그때는 빈 페이지가 나온다.
    """
    if channel_id is None and owner_user_id is None:
        return None

    ids: frozenset[uuid.UUID] | None = None
    if channel_id is not None:
        ids = frozenset(
            wiki_queries.list_artifact_ids_by_channel(
                db, workspace_id=workspace_id, channel_id=channel_id
            )
        )
    if owner_user_id is not None:
        owned = frozenset(
            wiki_queries.list_artifact_ids_by_owner(
                db, workspace_id=workspace_id, user_id=owner_user_id
            )
        )
        ids = owned if ids is None else ids & owned
    return ids


@router.get(
    path="/queue",
    response_model=QueuePageResponse,
    description=(
        "검토 대기 중인 문서 변경안 목록을 조회한다. "
        "정렬은 created_at 오름차순이다."
    ),
)
@audit_log(action=KnowledgeReviewAction.LIST)
def list_queue(
    contains_conflict: bool | None = Query(
        None,
        description="다툼(contested) 블록 유무로 거른다. 생략하면 전부 조회한다.",
    ),
    channel_id: uuid.UUID | None = Query(
        None, description="해당 채널 문서의 변경안만 조회한다."
    ),
    owner_user_id: int | None = Query(
        None,
        description="해당 사용자가 담당자인 문서의 변경안만 조회한다.",
    ),
    created_after: datetime | None = Query(
        None, description="해당 시각 이후에 만들어진 변경안만 조회한다."
    ),
    created_before: datetime | None = Query(
        None, description="해당 시각 이전에 만들어진 변경안만 조회한다."
    ),
    limit: int = Query(
        50, ge=1, le=200, description="한 페이지에 담을 변경안 수"
    ),
    offset: int = Query(0, ge=0, description="건너뛸 변경안 수"),
    context: ReviewerContext = Depends(resolve_member_reviewer_context),
    uow_factory: ReviewUowFactory = Depends(get_member_review_uow_factory),
    db: Session = Depends(get_db),
) -> QueuePageResponse:
    """검토 큐 한 페이지를 문서 위치·담당자·결정 가능 여부와 함께 돌려준다.

    목록은 workspace 구성원이면 누구나 연다. 줄마다 그 문서를 결정할 수
    있는지가 can_review로 실린다.

    위치와 담당자 조회는 페이지에 실린 문서 id로 한 번씩만 나간다. 줄마다
    조회하면 한 쪽에 문서 수만큼 질의가 붙는다.
    """
    page = list_review_queue(
        uow_factory(),
        workspace_id=context.workspace_id,
        contains_conflict=contains_conflict,
        artifact_ids=_queue_artifact_ids(
            db,
            workspace_id=context.workspace_id,
            channel_id=channel_id,
            owner_user_id=owner_user_id,
        ),
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )

    artifact_ids = [item.artifact_id for item in page.items]
    locations = wiki_queries.get_artifact_locations(
        db, artifact_ids=artifact_ids
    )
    owners = owners_by_artifact(db, artifact_ids)
    items = []
    for item in page.items:
        # 저장소에 없는 문서는 미분류로 읽는다. 담당자 지정 판정이 전역
        # 관리자 폴백으로 가고, 채널 관리자에게 열리지 않는다.
        artifact_channel_id, folder_id = locations.get(
            item.artifact_id, (None, None)
        )
        artifact_owners = owners[item.artifact_id]
        items.append(
            _to_queue_item(
                item,
                channel_id=artifact_channel_id,
                folder_id=folder_id,
                owners=artifact_owners,
                can_review=can_decide_artifact(
                    context.roles,
                    artifact_channel_id=artifact_channel_id,
                    artifact_id=item.artifact_id,
                    owner_user_ids=frozenset(
                        owner.user_id for owner in artifact_owners
                    ),
                    user_id=context.user.id,
                ),
            )
        )
    return QueuePageResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.get(
    path="/queue/{proposal_id}",
    response_model=ProposalDetailResponse,
    description=(
        "문서 변경안 하나를 블록·근거·발행판 대비 변경 목록·충돌과 함께 "
        "조회한다."
    ),
)
@audit_log(action=KnowledgeReviewAction.DETAIL)
def get_queue_item(
    proposal_id: uuid.UUID,
    context: ReviewerContext = Depends(resolve_member_reviewer_context),
    uow_factory: ReviewUowFactory = Depends(get_member_review_uow_factory),
    db: Session = Depends(get_db),
) -> ProposalDetailResponse:
    """변경안 하나를 충돌 목록·블록 결정과 함께 돌려준다.

    충돌은 본문의 다툼(contested) 블록에서만 나온다. 표시와 목록이 같은
    사실 하나에서 나오므로 둘이 서로 다른 이유로 어긋나지 않는다. 표시가
    켜졌는데 목록이 비는 것은 그 안건이 이미 결정돼 계류 목록에서 빠진
    경우이며, 그때도 표시는 본문에 다툼 블록이 있다는 사실 그대로다.

    상세는 workspace 구성원이면 열린다. 결정 가능 여부는
    can_review로 실어 보내고, 결정 경로는 저마다 같은 판정을 다시 한다.

    발행판은 문서마다 한 번만 읽는다. base_blocks와 block_changes가 같은
    한 벌에서 나와야 소비자가 두 값을 짝지어 볼 수 있다.

    문서 행은 읽기 레이아웃을 고르려고 읽는다. 어떤 양식으로 읽힐지는 문서
    종류가 정하는데, 변경안은 그 값을 들고 있지 않기 때문이다. 저장소에 없는
    문서면 종류를 모르는 것으로 두고 블록을 저장된 순서 그대로 낸다.

    Raises:
        HTTPException: 이 workspace에 그 변경안이 없으면 404를 던진다.
    """
    proposal = _load_proposal_for_view(uow_factory, proposal_id)
    channel_id, folder_id = wiki_queries.get_artifact_locations(
        db, artifact_ids=[proposal.artifact_id]
    ).get(proposal.artifact_id, (None, None))
    owners = owners_by_artifact(db, [proposal.artifact_id])[
        proposal.artifact_id
    ]
    can_review = can_decide_artifact(
        context.roles,
        artifact_channel_id=channel_id,
        artifact_id=proposal.artifact_id,
        owner_user_ids=frozenset(owner.user_id for owner in owners),
        user_id=context.user.id,
    )
    artifact = wiki_queries.get_artifact(
        db, artifact_id=proposal.artifact_id, workspace_id=context.workspace_id
    )
    revision = wiki_queries.get_latest_revision(
        db, artifact_id=proposal.artifact_id, workspace_id=context.workspace_id
    )
    base_blocks = (
        () if revision is None else deserialize_blocks(revision.blocks)
    )
    changes = diff_blocks(base_blocks, proposal.blocks)
    with uow_factory() as uow:
        verdicts = uow.block_verdicts.list_for_proposal(
            proposal_id=proposal_id,
        )
        contested_ids = _contested_contradiction_ids(proposal)
        contradictions = (
            uow.mutation_proposals.list_pending_contradictions(
                workspace_id=context.workspace_id,
            )
            if contested_ids
            else []
        )

    conflicts = [
        _to_conflict(item)
        for item in contradictions
        if item.id in contested_ids
    ]
    return _to_detail(
        proposal,
        conflicts=conflicts,
        verdicts=verdicts,
        channel_id=channel_id,
        folder_id=folder_id,
        owners=owners,
        can_review=can_review,
        base_blocks=base_blocks,
        changes=changes,
        kind=None if artifact is None else artifact.kind,
    )


@router.post(
    path="/artifacts/{proposal_id}/approve",
    response_model=DecisionResponse,
    description=(
        "문서 변경안 전체를 승인해 새 revision을 발행한다. "
        "블록 판정이 시작된 변경안에는 쓸 수 없다. "
        "문서 담당자만 할 수 있고, 담당자가 없는 문서는 워크스페이스 "
        "구성원 누구나 할 수 있다."
    ),
)
@audit_log(
    action=KnowledgeReviewAction.APPROVE,
    metadata_factory=KnowledgeReviewAuditMetadata.from_audit,
)
def approve_artifact(
    proposal_id: uuid.UUID,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
    db: Session = Depends(get_db),
) -> DecisionResponse:
    """승인을 확정하고 그 결과를 돌려준다.

    다툼 블록이 있거나 블록 결정이 이미 적혀 있는 안건은 서비스가 막고,
    여기서는 그 코드를 409로 옮긴다. 다툼 블록에는 통짜 승인이 승자를
    고를 자리가 없고, 적힌 블록 결정은 통짜 승인이 읽지 않아 반려된
    블록까지 판에 실리기 때문이다.

    담당자 규칙의 강제와 담당자 부여는 서비스가 자기 transaction 안에서
    한다. 여기 사전 검사는 서비스에 닿기 전에 빠르게 돌려보내는 자리일
    뿐이고, 확정을 가르는 것은 서비스의 재확인이다.

    Raises:
        HTTPException: 변경안이 없으면 404, 이 문서의 검수 권한이 없으면
            403, 다툼 블록이 있거나 블록 결정이 시작됐거나 결정을 받아들일
            수 없으면 409를 던진다.
    """
    _require_decidable_proposal(uow_factory, db, context, proposal_id)
    try:
        result = review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict=VERDICT_APPROVED,
            reviewer=context.reviewer,
            decider_user_id=context.user.id,
        )
    except ProposalReviewError as error:
        raise _artifact_review_error(
            uow_factory, proposal_id, code=error.code
        ) from error
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
    description=(
        "문서 변경안 전체를 사유와 함께 반려한다. "
        "문서 담당자만 할 수 있고, 담당자가 없는 문서는 워크스페이스 "
        "구성원 누구나 할 수 있다."
    ),
)
@audit_log(
    action=KnowledgeReviewAction.REJECT,
    metadata_factory=KnowledgeReviewAuditMetadata.from_audit,
)
def reject_artifact(
    proposal_id: uuid.UUID,
    payload: RejectRequest,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
    db: Session = Depends(get_db),
) -> DecisionResponse:
    """반려를 확정하고 그 결과를 돌려준다.

    사유 없는 반려는 서비스에 닿기 전에 막는다. 서비스와 DB도 같은 것을
    막지만, 그때는 "받아들일 수 없는 결정"과 구별되지 않는 409가 되어
    소비자가 입력을 고치면 되는 상황임을 알 수 없다.

    사유 검사를 인가보다 먼저 두는 이유도 같다. 보낸 값의 모양이 틀린 것은
    권한과 무관하고, 순서를 뒤집으면 소비자가 400을 받을 상황에서 404·403을
    받아 무엇을 고쳐야 하는지 알 수 없다.

    Raises:
        HTTPException: 사유가 비면 400, 변경안이 없으면 404, 이 문서의 검수
            권한이 없으면 403, 결정을 받아들일 수 없으면 409를 던진다.
    """
    if not payload.reason.strip():
        raise review_error(
            400,
            code="REASON_REQUIRED",
            message="반려는 사유가 있어야 합니다.",
        )
    _require_decidable_proposal(uow_factory, db, context, proposal_id)
    try:
        result = review_artifact_proposal(
            uow_factory(),
            proposal_id=proposal_id,
            verdict=VERDICT_REJECTED,
            reviewer=context.reviewer,
            reason=payload.reason,
            decider_user_id=context.user.id,
        )
    except ProposalReviewError as error:
        raise _artifact_review_error(
            uow_factory, proposal_id, code=error.code
        ) from error
    return DecisionResponse(
        proposal_id=str(result.proposal_id),
        verdict=result.verdict,
    )


@router.put(
    path="/queue/{proposal_id}/blocks/{block_index}/verdict",
    response_model=BlockVerdictResponse,
    description=(
        "변경안의 블록 하나에 승인 또는 반려를 기록한다. "
        "문서 담당자만 할 수 있고, 담당자가 없는 문서는 워크스페이스 "
        "구성원 누구나 할 수 있다."
    ),
)
@audit_log(
    action=KnowledgeReviewAction.BLOCK_VERDICT,
    metadata_factory=KnowledgeReviewAuditMetadata.from_audit,
)
def put_block_verdict(
    proposal_id: uuid.UUID,
    block_index: int,
    payload: BlockVerdictRequest,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
    db: Session = Depends(get_db),
) -> BlockVerdictResponse:
    """블록 결정을 저널에 남기고 그 결정을 돌려준다.

    같은 블록을 다시 눌러도 200이다. 마음을 바꾸는 것은 검토의 일부이고,
    서비스가 유일 제약 위에서 갱신으로 흡수한다.

    PUT인 이유가 그것이다. 블록당 결정은 하나뿐이라 같은 요청을 몇 번
    보내도 결과가 같다.

    Raises:
        HTTPException: 변경안이 없으면 404, 이 문서의 검수 권한이 없으면
            403, 이미 결정됐거나 본문이 바뀌었으면 409, 보낸 값 자체가
            틀렸으면 422를 던진다.
    """
    _require_decidable_proposal(uow_factory, db, context, proposal_id)
    try:
        stored = upsert_block_verdict(
            uow_factory(),
            proposal_id=proposal_id,
            block_index=block_index,
            block_content_hash_seen=payload.block_content_hash,
            verdict=payload.verdict,
            rejection_reason=payload.rejection_reason,
            chosen_winner_claim_id=payload.chosen_winner_claim_id,
            reviewer=context.reviewer,
        )
    except BlockVerdictError as error:
        status_code, message = _BLOCK_VERDICT_ERRORS.get(
            error.code, _UNMAPPED_ERROR
        )
        raise review_error(
            status_code, code=error.code, message=message
        ) from error
    return _to_block_verdict(stored)


@router.post(
    path="/queue/{proposal_id}/publish",
    response_model=PublishResponse,
    description=(
        "블록 판정을 마감한다. 승인 블록으로 새 revision을 발행하고, "
        "전부 반려면 변경안을 반려로 끝낸다. "
        "undecided로 미판정 블록을 일괄 승인 또는 반려할 수 있다. "
        "문서 담당자만 할 수 있고, 담당자가 없는 문서는 워크스페이스 "
        "구성원 누구나 할 수 있다."
    ),
)
@audit_log(
    action=KnowledgeReviewAction.PUBLISH,
    metadata_factory=KnowledgeReviewAuditMetadata.from_audit,
)
def publish_proposal(
    proposal_id: uuid.UUID,
    payload: PublishRequest,
    context: ReviewerContext = Depends(resolve_reviewer_workspace),
    uow_factory: ReviewUowFactory = Depends(get_review_uow_factory),
    db: Session = Depends(get_db),
) -> PublishResponse:
    """발행을 확정하고 그 결과를 돌려준다.

    미결정 블록이 남았으면 그 번호를 응답에 함께 싣는다. 코드만 돌려주면
    소비자는 검토자를 어느 블록으로 데려가야 하는지 알 수 없어 목록을
    처음부터 다시 훑게 된다.

    남은 블록을 일괄 반려하는데 사유가 비었으면 서비스에 닿기 전에 막는다.
    단건 반려와 같은 상황이므로 같은 400 REASON_REQUIRED로 답해야 소비자가
    입력만 고치면 되는 상황임을 알 수 있다.

    발행이 새 버전을 내면 담당자가 없던 문서에 발행한 사람을 담당자로
    세운다. 전 블록 반려로 끝난 발행은 문서의 내용을 확정한 것이 아니므로
    담당자를 만들지 않는다.

    Raises:
        HTTPException: 일괄 반려에 사유가 없으면 400, 변경안이 없으면 404,
            이 문서의 검수 권한이 없으면 403, 미결정·낡음·경합이면 409,
            보낸 값이나 조립 결과가 계약을 어기면 422를 던진다.
    """
    if payload.undecided == "reject" and not (
        payload.rejection_reason or ""
    ).strip():
        raise review_error(
            400,
            code="REASON_REQUIRED",
            message="반려는 사유가 있어야 합니다.",
        )
    _require_decidable_proposal(uow_factory, db, context, proposal_id)
    try:
        result = publish_artifact_proposal(
            uow_factory(),
            workspace_id=context.workspace_id,
            proposal_id=proposal_id,
            base_revision_id=payload.base_revision_id,
            reviewer=context.reviewer,
            undecided=payload.undecided,
            rejection_reason=payload.rejection_reason,
            decider_user_id=context.user.id,
        )
    except PublishError as error:
        if error.code == PUBLISH_CODE_NOT_DOCUMENT_OWNER:
            # 사전 검사를 지난 뒤 담당자가 지정된 경우다. 상태가 아니라
            # 권한 문제이므로 409 묶음에 섞지 않는다.
            raise _document_permission_error() from error
        status_code, message = _PUBLISH_ERRORS.get(
            error.code, _UNMAPPED_ERROR
        )
        extra = (
            {"undecided_block_indexes": list(error.undecided)}
            if error.undecided
            else None
        )
        raise review_error(
            status_code, code=error.code, message=message, extra=extra
        ) from error
    return PublishResponse(
        proposal_id=str(result.proposal_id),
        verdict=result.verdict,
        revision_id=(
            None if result.revision_id is None else str(result.revision_id)
        ),
        revision_number=result.revision_number,
        blocks_published=result.blocks_published,
        blocks_rejected=result.blocks_rejected,
        contradictions_resolved=result.contradictions_resolved,
        claims_accepted=result.claims_accepted,
    )


def _artifact_review_error(
    uow_factory: ReviewUowFactory,
    proposal_id: uuid.UUID,
    *,
    code: str | None = None,
) -> HTTPException:
    """문서 변경안 결정 실패를 상태 코드와 오류 코드로 옮긴다.

    서비스가 코드를 실어 보낸 거절은 그 코드로 바로 옮긴다. 무엇이
    막았는지 예외 자체가 말해 주므로 저장소를 다시 읽을 이유가 없다.

    코드가 없는 거절은 종류를 예외에서 읽을 수 없다. 그래서 실패한 뒤에
    저장소를 한 번 더 읽어 지금 상태로 코드를 정한다. 읽기 전용이고 결정
    규칙을 다시 판정하지 않는다 — 소비자가 무엇을 고쳐야 하는지 알려 주는
    진단일 뿐이다.
    """
    if code == REVIEW_CODE_NOT_DOCUMENT_OWNER:
        # 사전 검사를 지난 뒤 담당자가 지정된 경우다. 상태가 아니라 권한
        # 문제이므로 409 묶음에 섞지 않는다.
        return _document_permission_error()
    if code is not None:
        status_code, message = _ARTIFACT_REVIEW_ERRORS.get(
            code, _UNMAPPED_ERROR
        )
        return review_error(status_code, code=code, message=message)
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


def _to_queue_item(
    item: ReviewQueueItem,
    *,
    channel_id: uuid.UUID | None,
    folder_id: uuid.UUID | None,
    owners: list[OwnerResponse],
    can_review: bool,
) -> QueueItemResponse:
    """큐 한 줄을 문서 위치·담당자·결정 가능 여부와 함께 응답으로 옮긴다."""
    return QueueItemResponse(
        proposal_id=str(item.proposal_id),
        status=item.status,
        artifact=ArtifactRefResponse(
            id=str(item.artifact_id),
            title=item.title,
            channel_id=str(channel_id) if channel_id else None,
            folder_id=str(folder_id) if folder_id else None,
        ),
        summary=item.summary,
        origin=item.origin,
        contains_conflict=item.contains_conflict,
        created_at=item.created_at,
        owners=owners,
        can_review=can_review,
    )


def _has_contested(proposal: StoredArtifactProposal) -> bool:
    """이 변경안에 다툼 블록이 있는지 본다.

    충돌 표시의 유일한 근거다. 대상 노드나 subject_key로 되짚지 않는 이유는
    유도가 둘이면 둘이 어긋날 수 있기 때문이다.
    """
    return any(
        block.block_kind == BLOCK_KIND_CONTESTED for block in proposal.blocks
    )


def _contested_contradiction_ids(
    proposal: StoredArtifactProposal,
) -> set[uuid.UUID]:
    """다툼 블록들이 가리키는 모순 안건 식별자를 모은다."""
    return {
        contradiction_id
        for block in proposal.blocks
        if block.block_kind == BLOCK_KIND_CONTESTED
        for contradiction_id in block.proposal_ids
    }


def _to_block_verdict(stored: StoredBlockVerdict) -> BlockVerdictResponse:
    """저장된 블록 결정을 응답으로 옮긴다."""
    return BlockVerdictResponse(
        proposal_id=str(stored.proposal_id),
        block_index=stored.block_index,
        block_content_hash=stored.block_content_hash,
        verdict=stored.verdict,
        rejection_reason=stored.rejection_reason,
        chosen_winner_claim_id=(
            None
            if stored.chosen_winner_claim_id is None
            else str(stored.chosen_winner_claim_id)
        ),
        reviewer=stored.reviewer,
        reviewed_at=stored.reviewed_at,
    )


def _to_sources(
    sources: tuple[BlockSource, ...],
) -> list[BlockSourceResponse]:
    """근거 인용들을 응답으로 옮긴다."""
    return [
        BlockSourceResponse(
            claim_id=str(source.claim_id),
            statement=source.statement,
            observed_at=source.observed_at,
            citation_verified=source.citation_verified,
        )
        for source in sources
    ]


def _to_block(
    block: ArtifactBlock,
    *,
    block_index: int,
    verdict: StoredBlockVerdict | None,
    reason: str | None,
) -> BlockResponse:
    """블록 하나를 상세 응답의 블록으로 옮긴다.

    다툼 블록은 후보(variants)만 싣고 블록 자체의 sources는 비운다. 같은
    인용이 두 자리에 나오면 소비자가 어느 쪽을 정본으로 삼을지 알 수 없고,
    후보별로 갈린 근거가 한 덩어리로 뭉쳐 보인다.

    reason은 발행판과 견준 변경 사유다. 바뀌지 않은 블록은 없음으로 받는다.
    """
    contested = block.block_kind == BLOCK_KIND_CONTESTED
    return BlockResponse(
        block_index=block_index,
        block_kind=block.block_kind,
        heading=block.heading,
        body=block.body,
        claim_ids=[str(claim_id) for claim_id in block.claim_ids],
        proposal_ids=[str(item) for item in block.proposal_ids],
        ontology_version=block.ontology_version,
        block_content_hash=block_content_hash(block),
        narrative=block.narrative,
        relation_ids=[str(item) for item in block.relation_ids],
        sources=[] if contested else _to_sources(block.sources),
        variants=(
            [
                VariantResponse(
                    claim_id=str(variant.claim_id),
                    body=variant.body,
                    sources=_to_sources(variant.sources),
                )
                for variant in block.variants
            ]
            if contested
            else None
        ),
        verdict=None if verdict is None else _to_block_verdict(verdict),
        markdown=block_markdown(block),
        change_reason=reason,
    )


def _to_base_block(
    block: ArtifactBlock, *, block_index: int
) -> BaseBlockResponse:
    """발행판 블록 하나를 상세 응답의 발행판 블록으로 옮긴다.

    다툼 블록을 따로 다루지 않는다. 발행판에는 이미 승자가 정해진 문장만
    남으므로 후보를 나열할 자리가 없다.
    """
    return BaseBlockResponse(
        block_index=block_index,
        block_kind=block.block_kind,
        heading=block.heading,
        body=block.body,
        narrative=block.narrative,
        claim_ids=[str(claim_id) for claim_id in block.claim_ids],
        relation_ids=[str(item) for item in block.relation_ids],
        sources=_to_sources(block.sources),
    )


def _to_detail(
    proposal: StoredArtifactProposal,
    *,
    conflicts: list[ConflictResponse],
    verdicts: tuple[StoredBlockVerdict, ...],
    channel_id: uuid.UUID | None,
    folder_id: uuid.UUID | None,
    owners: list[OwnerResponse],
    can_review: bool,
    base_blocks: Sequence[ArtifactBlock],
    changes: tuple[BlockChange, ...],
    kind: str | None,
) -> ProposalDetailResponse:
    """변경안 하나를 상세 응답으로 옮긴다.

    변경 사유는 블록 자리로 짚어 붙인다. changes에는 바뀐 블록만 들어
    있으므로, 목록에 없는 자리의 블록은 사유가 없음이 된다. 발행판이 없는
    신규 문서는 사유를 아예 붙이지 않는다.

    읽기 레이아웃은 변경안 블록과 발행판 블록에 각각 따로 만든다. 둘은 블록
    구성이 다르므로 한쪽의 자리 번호를 다른 쪽에 쓸 수 없다. kind를 모르면
    레이아웃이 없어 블록을 저장된 순서 그대로 낸다.
    """
    contains_conflict = _has_contested(proposal)
    by_index = {verdict.block_index: verdict for verdict in verdicts}
    # 발행판이 없으면 문서 전체가 새것이라 블록마다 사유를 붙여도
    # 같은 말이 되풀이될 뿐이라 붙이지 않는다.
    reasons = (
        {
            change.block_index: change_reason(
                change, base=base_blocks, proposed=proposal.blocks
            )
            for change in changes
            if change.block_index is not None
        }
        if base_blocks
        else {}
    )
    claim_ids: dict[str, None] = {}
    proposal_ids: dict[str, None] = {}
    relation_ids: dict[str, None] = {}
    blocks: list[BlockResponse] = []
    for index, block in enumerate(proposal.blocks):
        for claim_id in block.claim_ids:
            claim_ids.setdefault(str(claim_id), None)
        for item in block.proposal_ids:
            proposal_ids.setdefault(str(item), None)
        for relation_id in block.relation_ids:
            relation_ids.setdefault(str(relation_id), None)
        blocks.append(
            _to_block(
                block,
                block_index=index,
                verdict=by_index.get(index),
                reason=reasons.get(index),
            )
        )
    return ProposalDetailResponse(
        proposal_id=str(proposal.id),
        status=proposal.status,
        artifact=ArtifactRefResponse(
            id=str(proposal.artifact_id),
            title=proposal.title,
            channel_id=str(channel_id) if channel_id else None,
            folder_id=str(folder_id) if folder_id else None,
        ),
        origin=proposal.origin,
        created_at=proposal.created_at,
        base_revision_id=(
            None
            if proposal.base_revision_id is None
            else str(proposal.base_revision_id)
        ),
        contains_conflict=contains_conflict,
        owners=owners,
        can_review=can_review,
        blocks=blocks,
        layout=layout_items(proposal.blocks, kind=kind),
        base_blocks=[
            _to_base_block(block, block_index=index)
            for index, block in enumerate(base_blocks)
        ],
        # 발행판이 없으면 자리표시조차 내지 않는다. 빈 칸 목록은 "값이
        # 아직 없는 발행판"으로 읽히는데, 실제로는 발행된 판 자체가 없다.
        base_layout=(
            layout_items(base_blocks, kind=kind) if base_blocks else []
        ),
        block_changes=[
            BlockChangeResponse(
                change=change.change,
                block_index=change.block_index,
                base_block_index=change.base_block_index,
            )
            for change in changes
        ],
        read_set=ReadSetResponse(
            claim_ids=list(claim_ids),
            proposal_ids=list(proposal_ids),
            relation_ids=list(relation_ids),
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
