"""블록 단위 결정 기록을 fake 저장소 위에서 확인한다.

fake는 실 DB의 제약을 흉내 낸다. `(proposal_id, block_index)` UNIQUE로
같은 블록의 재결정을 덮어쓰고, verdict 값·반려 사유·결정자 공백 CHECK를
그대로 막는다. 제약을 흉내 내지 않는 fake는 서비스가 조용히 어긴 규칙을
통과시킨다.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from typing import Any

import pytest

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.services.review_block_verdict import (
    BlockVerdictError,
)
from catchup.knowledge_maintenance.services.review_block_verdict import (
    upsert_block_verdict,
)

REVIEWER = "tester"
CREATED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def _claim_block(body: str = "2026-09") -> ArtifactBlock:
    """근거를 갖춘 claim_section 블록 하나를 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="release_month",
        body=body,
        claim_ids=(uuid.uuid4(),),
        proposal_ids=(),
        ontology_version="1",
    )


def _contested_block(
    winners: tuple[uuid.UUID, uuid.UUID],
    *,
    extra_claim_id: uuid.UUID | None = None,
) -> ArtifactBlock:
    """후보 둘을 나란히 세운 contested 블록 하나를 만든다.

    extra_claim_id는 claim_ids에만 있고 variants에는 없는 claim을 심는다.
    승자 검증이 claim_ids 전체가 아니라 variants를 본다는 것을 드러낸다.
    """
    claim_ids = list(winners)
    if extra_claim_id is not None:
        claim_ids.append(extra_claim_id)
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CONTESTED,
        heading="release_month",
        body="",
        claim_ids=tuple(claim_ids),
        proposal_ids=(uuid.uuid4(),),
        ontology_version="1",
        variants=tuple(
            ContestedVariant(claim_id=claim_id, body=f"후보 {index}", sources=())
            for index, claim_id in enumerate(winners)
        ),
    )


class FakeArtifactRepository:
    """artifact 저장소를 대신한다. 블록은 실 DB처럼 직렬화해 담는다."""

    def __init__(self) -> None:
        self.proposals: dict[uuid.UUID, dict[str, Any]] = {}

    def add_proposal(
        self,
        *,
        blocks: tuple[ArtifactBlock, ...],
        status: str = "pending",
    ) -> uuid.UUID:
        """테스트가 쓸 변경안 한 건을 미리 넣는다."""
        proposal_id = uuid.uuid4()
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "artifact_id": uuid.uuid4(),
            "subject_node_id": uuid.uuid4(),
            "title": "결제 기능",
            "status": status,
            "blocks": serialize_blocks(blocks),
            "content_hash": "0" * 64,
            "base_revision_id": None,
            "rejection_reason": None,
            "origin": "compiled",
            "created_at": CREATED_AT,
        }
        return proposal_id

    def get_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
    ) -> StoredArtifactProposal | None:
        row = self.proposals.get(proposal_id)
        if row is None:
            return None
        return StoredArtifactProposal(
            id=row["id"],
            artifact_id=row["artifact_id"],
            subject_node_id=row["subject_node_id"],
            title=row["title"],
            status=row["status"],
            blocks=deserialize_blocks(row["blocks"]),
            content_hash=row["content_hash"],
            base_revision_id=row["base_revision_id"],
            rejection_reason=row["rejection_reason"],
            origin=row["origin"],
            created_at=row["created_at"],
        )


class FakeBlockVerdictRepository:
    """블록 결정 저장소를 DB 제약까지 흉내 내어 대신한다.

    `(proposal_id, block_index)` UNIQUE를 dict 키로 재현하므로 같은 블록을
    다시 판정하면 행이 늘지 않고 덮인다. verdict 값·반려 사유·결정자 공백
    CHECK도 그대로 막는다.
    """

    def __init__(self, proposals: dict[uuid.UUID, dict[str, Any]]) -> None:
        self._proposals = proposals
        self.verdicts: dict[tuple[uuid.UUID, int], dict[str, Any]] = {}

    def upsert_verdict(
        self,
        *,
        proposal_id: uuid.UUID,
        block_index: int,
        block_content_hash: str,
        verdict: str,
        rejection_reason: str | None,
        chosen_winner_claim_id: uuid.UUID | None,
        reviewer: str,
        reviewed_at: datetime,
    ) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"변경안 {proposal_id}가 없다")
        if verdict not in ("approved", "rejected"):
            raise ValueError(f"약속되지 않은 판정 {verdict}")
        if verdict == "rejected" and not (rejection_reason or "").strip():
            raise ValueError("반려는 사유가 있어야 한다")
        if not reviewer.strip():
            raise ValueError("결정자가 있어야 한다")
        self.verdicts[(proposal_id, block_index)] = {
            "proposal_id": proposal_id,
            "block_index": block_index,
            "block_content_hash": block_content_hash,
            "verdict": verdict,
            "rejection_reason": rejection_reason,
            "chosen_winner_claim_id": chosen_winner_claim_id,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
        }

    def list_for_proposal(
        self, *, proposal_id: uuid.UUID
    ) -> tuple[StoredBlockVerdict, ...]:
        rows = [
            row
            for row in self.verdicts.values()
            if row["proposal_id"] == proposal_id
        ]
        rows.sort(key=lambda row: row["block_index"])
        return tuple(StoredBlockVerdict(**row) for row in rows)

    def find_rejected_hashes(
        self, *, artifact_id: uuid.UUID
    ) -> dict[str, str]:
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.artifacts = FakeArtifactRepository()
        self.block_verdicts = FakeBlockVerdictRepository(
            self.artifacts.proposals
        )
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed = True


def _approve(
    uow: FakeUnitOfWork,
    proposal_id: uuid.UUID,
    block: ArtifactBlock,
    **overrides: Any,
) -> StoredBlockVerdict:
    """정상 승인 한 번을 부른다. overrides로 한 인자만 비튼다."""
    kwargs: dict[str, Any] = {
        "proposal_id": proposal_id,
        "block_index": 0,
        "block_content_hash_seen": block_content_hash(block),
        "verdict": "approved",
        "rejection_reason": None,
        "chosen_winner_claim_id": None,
        "reviewer": REVIEWER,
        "now": NOW,
    }
    kwargs.update(overrides)
    return upsert_block_verdict(uow, **kwargs)


def test_approve_records_verdict() -> None:
    """정상 승인은 결정을 한 줄 남기고 transaction을 확정한다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    result = _approve(uow, proposal_id, block)

    assert result.proposal_id == proposal_id
    assert result.block_index == 0
    assert result.block_content_hash == block_content_hash(block)
    assert result.verdict == "approved"
    assert result.rejection_reason is None
    assert result.chosen_winner_claim_id is None
    assert result.reviewer == REVIEWER
    assert result.reviewed_at == NOW
    assert uow.committed is True
    assert uow.block_verdicts.list_for_proposal(
        proposal_id=proposal_id
    ) == (result,)


def test_redeciding_same_block_overwrites_single_row() -> None:
    """사람이 마음을 바꿔 다시 누르면 행이 늘지 않고 덮인다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    _approve(uow, proposal_id, block)
    result = _approve(
        uow,
        proposal_id,
        block,
        verdict="rejected",
        rejection_reason="근거가 약하다",
    )

    stored = uow.block_verdicts.list_for_proposal(proposal_id=proposal_id)
    assert stored == (result,)
    assert stored[0].verdict == "rejected"
    assert stored[0].rejection_reason == "근거가 약하다"


def test_contested_approval_records_chosen_winner() -> None:
    """contested 승인은 사람이 고른 승자를 함께 남긴다."""
    uow = FakeUnitOfWork()
    winners = (uuid.uuid4(), uuid.uuid4())
    block = _contested_block(winners)
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    result = _approve(
        uow, proposal_id, block, chosen_winner_claim_id=winners[1]
    )

    assert result.chosen_winner_claim_id == winners[1]


def test_unknown_proposal_is_not_found() -> None:
    """없는 변경안에 대한 결정은 NOT_FOUND로 거절한다."""
    uow = FakeUnitOfWork()
    block = _claim_block()

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, uuid.uuid4(), block)

    assert error.value.code == "NOT_FOUND"
    assert uow.committed is False


@pytest.mark.parametrize("status", ["approved", "rejected", "applied"])
def test_decided_proposal_is_refused(status: str) -> None:
    """이미 결정된 변경안의 블록은 다시 판정하지 않는다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,), status=status)

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block)

    assert error.value.code == "ALREADY_DECIDED"


@pytest.mark.parametrize("block_index", [-1, 1, 99])
def test_block_index_out_of_range_is_invalid(block_index: int) -> None:
    """변경안에 없는 블록 번호는 INVALID로 거절한다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block, block_index=block_index)

    assert error.value.code == "INVALID"


def test_changed_block_content_is_stale() -> None:
    """검토자가 본 내용과 지금 내용이 다르면 STALE_BLOCK이다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))
    seen = block_content_hash(_claim_block("2026-10"))

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block, block_content_hash_seen=seen)

    assert error.value.code == "STALE_BLOCK"
    assert uow.committed is False


def test_unknown_verdict_is_invalid() -> None:
    """약속되지 않은 verdict는 저장소에 닿기 전에 막는다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block, verdict="maybe")

    assert error.value.code == "INVALID"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_rejection_without_reason_is_invalid(reason: str | None) -> None:
    """사유 없는 반려는 감사 기록이 되지 못하므로 막는다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(
            uow,
            proposal_id,
            block,
            verdict="rejected",
            rejection_reason=reason,
        )

    assert error.value.code == "INVALID"


def test_contested_approval_without_winner_is_invalid() -> None:
    """contested 승인은 승자를 고르지 않으면 성립하지 않는다."""
    uow = FakeUnitOfWork()
    block = _contested_block((uuid.uuid4(), uuid.uuid4()))
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block)

    assert error.value.code == "INVALID"


def test_contested_winner_outside_variants_is_invalid() -> None:
    """승자는 variants 안에서만 고를 수 있다. claim_ids로는 넓지 않다."""
    uow = FakeUnitOfWork()
    outsider = uuid.uuid4()
    block = _contested_block(
        (uuid.uuid4(), uuid.uuid4()), extra_claim_id=outsider
    )
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block, chosen_winner_claim_id=outsider)

    assert error.value.code == "INVALID"


def test_winner_on_non_contested_block_is_invalid() -> None:
    """다툼이 없는 블록에 승자를 지정하면 뜻이 없으므로 막는다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(
            uow,
            proposal_id,
            block,
            chosen_winner_claim_id=block.claim_ids[0],
        )

    assert error.value.code == "INVALID"


@pytest.mark.parametrize("reviewer", ["", "   "])
def test_blank_reviewer_is_invalid(reviewer: str) -> None:
    """결정자가 없는 판정은 감사 기록이 되지 못한다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))

    with pytest.raises(BlockVerdictError) as error:
        _approve(uow, proposal_id, block, reviewer=reviewer)

    assert error.value.code == "INVALID"


def test_now_defaults_to_current_time() -> None:
    """호출자가 시각을 주지 않으면 지금 시각을 찍는다."""
    uow = FakeUnitOfWork()
    block = _claim_block()
    proposal_id = uow.artifacts.add_proposal(blocks=(block,))
    before = datetime.now(UTC)

    result = _approve(uow, proposal_id, block, now=None)

    assert before <= result.reviewed_at <= datetime.now(UTC)
