"""사람이 블록 하나에 내린 결정을 저널에 기록한다.

변경안 전체를 한 번에 승인하거나 반려하는 판정과 달리, 여기서는 블록
하나만 본다. 검토자가 문서의 어떤 부분은 받아들이고 어떤 부분은 되돌려
보낼 수 있어야 하기 때문이다. 확정(발행)은 이 서비스가 하지 않는다. 이
자리는 사람이 누른 것을 그대로 적어 두는 저널일 뿐이고, 모아서 새 판을
만드는 일은 발행 서비스의 몫이다.

결정에는 그 결정이 무엇을 보고 내려졌는지를 함께 못박는다. 검토자가
화면에서 본 블록 내용의 지문을 받아, 지금 변경안의 그 블록과 다르면
거절한다. 다르다는 것은 검토자가 본 문장과 지금 저장된 문장이 같지
않다는 뜻이고, 그대로 적으면 사람이 읽지 않은 내용에 사람의 이름이
붙는다.

같은 블록을 다시 누르는 것은 오류가 아니라 마음을 바꾼 것이다. 블록당
한 줄이라는 유일 제약 위에서 갱신으로 흡수하고, 마지막 결정만 남긴다.

담당자 규칙도 이 transaction 안에서 본다. 판정은 발행이 읽어 확정하는
재료이므로, 여기가 규칙 밖에 있으면 담당자가 지정된 뒤에도 남이 적어 둔
판정이 담당자의 발행을 타고 문서에 실린다.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.block_verdicts import BlockVerdictRepository
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

BLOCK_VERDICT_APPROVED = "approved"
BLOCK_VERDICT_REJECTED = "rejected"

_BLOCK_VERDICTS = (BLOCK_VERDICT_APPROVED, BLOCK_VERDICT_REJECTED)

PROPOSAL_STATUS_PENDING = "pending"

# 거절 사유를 가르는 코드다. 호출자는 이 값으로 응답을 정한다.
CODE_NOT_FOUND = "PROPOSAL_NOT_FOUND"
CODE_ALREADY_DECIDED = "ALREADY_DECIDED"
CODE_STALE_BLOCK = "STALE_BLOCK"
CODE_INVALID = "INVALID"
# 담당자가 정해진 문서에 담당자가 아닌 사람이 판정을 적으려 한 경우다.
# 호출자는 이것만 권한 응답으로 옮기고 나머지는 상태 응답으로 옮긴다.
CODE_NOT_DOCUMENT_OWNER = "NOT_DOCUMENT_OWNER"


class BlockVerdictError(Exception):
    """블록 결정을 받아들일 수 없음을 알린다. code로 사유를 가른다.

    하나의 예외로 모으되 code를 남기는 이유는, 호출자가 사유마다 다르게
    응대해야 하기 때문이다. PROPOSAL_NOT_FOUND와 ALREADY_DECIDED는 목록을 다시
    읽어야 하고, STALE_BLOCK은 검토자에게 바뀐 본문을 다시 보여 줘야
    하며, INVALID는 보낸 값 자체가 틀린 것이다. 문자열 메시지를 뜯어
    보게 두지 않으려고 코드를 필드로 세운다.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class BlockVerdictUnitOfWork(Protocol):
    """블록 결정 기록이 쓰는 transaction 경계를 정의한다.

    변경안을 읽는 저장소와 결정을 쓰는 저장소만 있다. 이 서비스는 판을
    쌓지도 claim을 확정하지도 않으므로, 그 저장소에 접근 자체가 없어야
    "저널만 쓴다"는 것이 구조로 보장된다.
    """

    artifacts: ArtifactRepository
    block_verdicts: BlockVerdictRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


def upsert_block_verdict(
    uow: BlockVerdictUnitOfWork,
    *,
    proposal_id: uuid.UUID,
    block_index: int,
    block_content_hash_seen: str,
    verdict: str,
    rejection_reason: str | None,
    chosen_winner_claim_id: uuid.UUID | None,
    reviewer: str,
    now: datetime | None = None,
    decider_user_id: int | None = None,
) -> StoredBlockVerdict:
    """블록 하나의 결정을 확정해 저널에 남기고 그 결정을 돌려준다.

    같은 블록에 이미 결정이 있으면 갱신으로 흡수한다. 마음을 바꾸는 것은
    검토의 일부이므로 오류가 아니다.

    `decider_user_id`를 주면 담당자 규칙을 이 transaction 안에서 강제한다.
    문서에 담당자가 있고 결정자가 그중에 없으면 거절한다. 판정은 발행이
    읽어 확정하는 재료이므로, 여기에 규칙이 없으면 담당자가 지정된 뒤에도
    남이 적어 둔 판정이 담당자의 발행을 타고 문서에 실린다. 담당자를
    세우는 일은 여기서 하지 않는다 — 블록 판정은 문서의 내용을 확정한
    것이 아니라 확정을 위한 재료다.

    주지 않으면 강제하지 않는다. CLI 러너와 debug 표면이 이 경로다.

    Raises:
        BlockVerdictError: 결정을 받아들일 수 없을 때 던진다. code는
            PROPOSAL_NOT_FOUND·ALREADY_DECIDED·STALE_BLOCK·INVALID·
            NOT_DOCUMENT_OWNER 중 하나다.
    """
    if not reviewer.strip():
        # 누가 결정했는지 없는 판정은 감사 기록이 되지 못한다.
        raise BlockVerdictError(CODE_INVALID, "결정자가 비어 있다")
    reviewed_at = datetime.now(UTC) if now is None else now

    with uow:
        # 일괄 발행과 같은 행을 잠근다. 두 경로가 이 행 하나를 두고 줄을
        # 서야 한쪽의 미결정 판단이 다른 쪽 때문에 도중에 어긋나지 않는다.
        proposal = uow.artifacts.get_proposal(
            proposal_id=proposal_id, for_update=True
        )
        if proposal is None:
            # 저장소가 workspace를 고정하므로, 남의 workspace 변경안도
            # 여기서는 없는 것과 같다.
            raise BlockVerdictError(
                CODE_NOT_FOUND, f"변경안 {proposal_id}를 찾을 수 없다"
            )
        if proposal.status != PROPOSAL_STATUS_PENDING:
            raise BlockVerdictError(
                CODE_ALREADY_DECIDED,
                f"변경안 {proposal_id}는 이미 {proposal.status} 상태다",
            )
        if decider_user_id is not None:
            # 변경안 행을 잠근 뒤에 본다. 문서 행은 그 잠금이 이미 잡았고,
            # 담당자 명단을 바꾸는 경로도 같은 문서 행을 잡으므로 판정과
            # 지정이 그 행 하나를 두고 줄을 선다.
            owner_user_ids = uow.artifacts.lock_owner_user_ids(
                artifact_id=proposal.artifact_id
            )
            if owner_user_ids and decider_user_id not in owner_user_ids:
                raise BlockVerdictError(
                    CODE_NOT_DOCUMENT_OWNER,
                    f"변경안 {proposal_id}의 문서는 담당자만 판정할 수 있다",
                )
        if not 0 <= block_index < len(proposal.blocks):
            raise BlockVerdictError(
                CODE_INVALID,
                f"블록 번호 {block_index}가 변경안 범위를 벗어났다",
            )

        block = proposal.blocks[block_index]
        current_hash = block_content_hash(block)
        if current_hash != block_content_hash_seen:
            # 검토자가 본 본문과 지금 본문이 다르다. 여기서 적으면 읽지
            # 않은 문장에 사람의 이름이 붙으므로, 다시 보게 돌려보낸다.
            raise BlockVerdictError(
                CODE_STALE_BLOCK,
                f"블록 {block_index}의 내용이 검토 시점과 다르다",
            )

        if verdict not in _BLOCK_VERDICTS:
            raise BlockVerdictError(
                CODE_INVALID, f"알 수 없는 verdict {verdict!r}"
            )
        if verdict == BLOCK_VERDICT_REJECTED and not (
            rejection_reason or ""
        ).strip():
            raise BlockVerdictError(CODE_INVALID, "반려는 사유가 있어야 한다")

        _validate_winner(
            block_kind=block.block_kind,
            variant_claim_ids=frozenset(
                variant.claim_id for variant in block.variants
            ),
            verdict=verdict,
            chosen_winner_claim_id=chosen_winner_claim_id,
        )

        uow.block_verdicts.upsert_verdict(
            proposal_id=proposal_id,
            block_index=block_index,
            block_content_hash=current_hash,
            verdict=verdict,
            rejection_reason=rejection_reason,
            chosen_winner_claim_id=chosen_winner_claim_id,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        uow.commit()

    logger.info(
        "artifact_block_verdict_recorded",
        proposal_id=str(proposal_id),
        artifact_id=str(proposal.artifact_id),
        block_index=block_index,
        verdict=verdict,
        chosen_winner_claim_id=(
            None
            if chosen_winner_claim_id is None
            else str(chosen_winner_claim_id)
        ),
        reviewer=reviewer,
    )
    return StoredBlockVerdict(
        proposal_id=proposal_id,
        block_index=block_index,
        block_content_hash=current_hash,
        verdict=verdict,
        rejection_reason=rejection_reason,
        chosen_winner_claim_id=chosen_winner_claim_id,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
    )


def _validate_winner(
    *,
    block_kind: str,
    variant_claim_ids: frozenset[uuid.UUID],
    verdict: str,
    chosen_winner_claim_id: uuid.UUID | None,
) -> None:
    """승자 지정이 블록 종류와 맞는지 검사한다.

    contested 블록의 승인은 곧 "이 후보가 맞다"는 결정이므로 승자가
    있어야 하고, 그 승자는 화면에 나란히 놓였던 후보 중 하나여야 한다.
    허용 집합이 claim_ids가 아니라 variants인 이유는, contested 블록의
    claim_ids에는 후보로 렌더되지 않은 claim도 섞일 수 있어 넓게 잡으면
    검토자가 고르지 않은 claim이 승자로 적힐 수 있기 때문이다.

    반대로 다툼이 없는 블록의 승자 지정은 가리킬 대상이 없는 값이다.
    조용히 버리면 호출자는 자기가 보낸 선택이 반영된 줄 안다.

    Raises:
        BlockVerdictError: 승자 지정이 블록 종류와 어긋날 때 던진다.
    """
    if block_kind != BLOCK_KIND_CONTESTED:
        if chosen_winner_claim_id is not None:
            raise BlockVerdictError(
                CODE_INVALID, "다툼 블록이 아닌데 승자가 지정됐다"
            )
        return
    if verdict != BLOCK_VERDICT_APPROVED:
        return
    if chosen_winner_claim_id is None:
        raise BlockVerdictError(
            CODE_INVALID, "다툼 블록 승인은 승자를 골라야 한다"
        )
    if chosen_winner_claim_id not in variant_claim_ids:
        raise BlockVerdictError(
            CODE_INVALID,
            f"승자 {chosen_winner_claim_id}가 후보에 없다",
        )
