"""블록 결정을 모아 한 판으로 발행하는 조립을 fake 위에서 확인한다.

이 서비스가 지키는 것은 세 가지다. 승인된 블록만 판에 오르는 것,
다툼 블록의 승자가 모순 결정으로도 함께 흘러가는 것, 그리고 그 둘이
하나의 transaction에서만 일어나는 것이다. fake는 실 DB의 제약을 흉내
낸다 — 판 번호 UNIQUE, 계류 행에만 걸리는 결정 전이, 반려 사유 CHECK.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from types import TracebackType
from typing import Any
from typing import Self

import pytest
from sqlalchemy.exc import IntegrityError

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import BlockSource
from catchup.knowledge_maintenance.domain.artifact import ContestedVariant
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    PublishError,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    publish_artifact_proposal,
)

WORKSPACE_ID = 1
REVIEWER = "user:ba2slk"
CREATED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
DECIDED_AT = datetime(2026, 8, 9, 9, 0, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 7, 20, tzinfo=UTC)
EARLY = datetime(2026, 7, 1, tzinfo=UTC)
LATER = datetime(2026, 7, 20, tzinfo=UTC)


def _source(claim_id: uuid.UUID, statement: str) -> BlockSource:
    """근거 인용 하나를 만든다."""
    return BlockSource(
        claim_id=claim_id,
        statement=statement,
        observed_at=OBSERVED_AT,
        citation_verified=True,
    )


def _claim_block(claim_id: uuid.UUID, heading: str) -> ArtifactBlock:
    """근거를 갖춘 claim_section 블록 하나를 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading=heading,
        body=f"{heading} 본문",
        claim_ids=(claim_id,),
        proposal_ids=(),
        ontology_version="1",
        sources=(_source(claim_id, f"{heading} 근거"),),
    )


def _contested_block(
    *,
    heading: str,
    contradiction_id: uuid.UUID,
    first: uuid.UUID,
    second: uuid.UUID,
) -> ArtifactBlock:
    """후보 둘을 나란히 놓은 contested 블록 하나를 만든다."""
    return ArtifactBlock(
        block_kind=BLOCK_KIND_CONTESTED,
        heading=heading,
        body="상충하는 값 2개 — 검토 필요",
        claim_ids=(first, second),
        proposal_ids=(contradiction_id,),
        ontology_version="1",
        sources=(_source(first, "후보 1 근거"), _source(second, "후보 2 근거")),
        variants=(
            ContestedVariant(
                claim_id=first,
                body="60 (2026-07-20 관찰)",
                sources=(_source(first, "후보 1 근거"),),
            ),
            ContestedVariant(
                claim_id=second,
                body="120 (2026-07-20 관찰)",
                sources=(_source(second, "후보 2 근거"),),
            ),
        ),
    )


class FakeArtifactRepository:
    """artifact 저장소를 DB 제약까지 흉내 내어 대신한다.

    블록은 실 DB처럼 직렬화해 담았다가 읽을 때 되돌린다. 판 번호
    UNIQUE는 실 DB와 같은 `IntegrityError`로 막고, 결정 쓰기는 계류
    행에만 걸리는 낙관적 전이를 재현한다. 조용히 통과시키는 fake는
    서비스가 어긴 규칙을 초록으로 덮는다.
    """

    def __init__(self) -> None:
        self.proposals: dict[uuid.UUID, dict[str, Any]] = {}
        self.revisions: list[dict[str, Any]] = []

    def add_proposal(
        self,
        *,
        artifact_id: uuid.UUID,
        blocks: tuple[ArtifactBlock, ...],
        base_revision_id: uuid.UUID | None,
        status: str = "pending",
    ) -> uuid.UUID:
        """테스트가 쓸 변경안 한 건을 미리 넣는다."""
        proposal_id = uuid.uuid4()
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "artifact_id": artifact_id,
            "subject_node_id": uuid.uuid4(),
            "title": "결제 기능",
            "status": status,
            "blocks": serialize_blocks(blocks),
            "content_hash": "0" * 64,
            "base_revision_id": base_revision_id,
            "rejection_reason": None,
            "reviewer": None,
            "origin": "compiled",
            "created_at": CREATED_AT,
        }
        return proposal_id

    def get_proposal(
        self, *, proposal_id: uuid.UUID
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

    def find_latest_revision_id_and_number(
        self, *, artifact_id: uuid.UUID
    ) -> tuple[uuid.UUID, int] | None:
        found = [
            row for row in self.revisions if row["artifact_id"] == artifact_id
        ]
        if not found:
            return None
        latest = max(found, key=lambda row: row["revision_number"])
        return latest["id"], latest["revision_number"]

    def add_revision(
        self,
        *,
        artifact_id: uuid.UUID,
        revision_number: int,
        blocks: Any,
        source_proposal_id: uuid.UUID,
    ) -> uuid.UUID:
        for row in self.revisions:
            if (
                row["artifact_id"] == artifact_id
                and row["revision_number"] == revision_number
            ):
                raise IntegrityError(
                    "INSERT INTO knowledge_artifact_revisions",
                    None,
                    Exception("같은 판 번호가 이미 있다"),
                )
        revision_id = uuid.uuid4()
        self.revisions.append(
            {
                "id": revision_id,
                "artifact_id": artifact_id,
                "revision_number": revision_number,
                "blocks": serialize_blocks(tuple(blocks)),
                "source_proposal_id": source_proposal_id,
            }
        )
        return revision_id

    def revision_blocks(
        self, revision_id: uuid.UUID
    ) -> tuple[ArtifactBlock, ...]:
        """저장된 판의 블록을 되돌려 읽는다."""
        row = next(
            item for item in self.revisions if item["id"] == revision_id
        )
        return deserialize_blocks(row["blocks"])

    def _pending_row(self, proposal_id: uuid.UUID) -> dict[str, Any]:
        """계류 중인 행만 내준다. 아니면 실 저장소처럼 던진다."""
        row = self.proposals.get(proposal_id)
        if row is None or row["status"] != "pending":
            raise ProposalAlreadyDecided(
                f"변경안 {proposal_id}는 계류 중이 아니다"
            )
        return row

    def mark_approved(self, *, proposal_id: uuid.UUID, reviewer: str) -> None:
        row = self._pending_row(proposal_id)
        row["status"] = "approved"
        row["reviewer"] = reviewer

    def mark_rejected(
        self, *, proposal_id: uuid.UUID, reviewer: str, reason: str
    ) -> None:
        if not (reason or "").strip():
            raise ValueError("반려는 사유가 있어야 한다")
        row = self._pending_row(proposal_id)
        row["status"] = "rejected"
        row["reviewer"] = reviewer
        row["rejection_reason"] = reason


class FakeBlockVerdictRepository:
    """블록 결정 저장소를 DB 제약까지 흉내 내어 대신한다.

    `(proposal_id, block_index)` UNIQUE를 dict 키로 재현한다. verdict
    값·반려 사유·결정자 공백 CHECK도 그대로 막는다.
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
        rows = [
            row
            for row in self.verdicts.values()
            if row["verdict"] == "rejected"
            and self._artifact_id(row["proposal_id"]) == artifact_id
        ]
        rows.sort(key=lambda row: (row["reviewed_at"], row["block_index"]))
        return {
            row["block_content_hash"]: row["rejection_reason"] or ""
            for row in rows
        }

    def _artifact_id(self, proposal_id: uuid.UUID) -> uuid.UUID | None:
        row = self._proposals.get(proposal_id)
        return None if row is None else row["artifact_id"]


@dataclass
class FakeMutationRepository:
    """모순 안건 저장소를 계류 전이까지 흉내 내어 대신한다."""

    proposals: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    operations: dict[uuid.UUID, list[dict[str, Any]]] = field(
        default_factory=dict
    )

    def add_contradiction(
        self, *, claim_ids: tuple[uuid.UUID, ...], status: str = "pending"
    ) -> uuid.UUID:
        """테스트가 쓸 모순 안건 한 건을 미리 넣는다."""
        proposal_id = uuid.uuid4()
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "status": status,
            "predicate": "rate_limit_per_minute",
            "subject_key": "node:abc",
            "summary": "값이 2종으로 갈린다",
            "reviewer": None,
            "decision": None,
            "values": tuple(
                StoredContradictionValue(
                    claim_id=claim_id,
                    value=60 * (index + 1),
                    normalized=str(60 * (index + 1)),
                    statement=f"주장 {index}",
                    observed_at="2026-07-20T00:00:00+00:00",
                )
                for index, claim_id in enumerate(claim_ids)
            ),
        }
        self.operations[proposal_id] = []
        return proposal_id

    def list_pending_contradictions(
        self, *, workspace_id: int
    ) -> list[StoredContradictionProposal]:
        return [
            StoredContradictionProposal(
                id=row["id"],
                predicate=row["predicate"],
                subject_key=row["subject_key"],
                summary=row["summary"],
                values=row["values"],
            )
            for row in self.proposals.values()
            if row["status"] == "pending"
        ]

    def record_contradiction_decision(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        decision: dict[str, Any],
        supersede_targets: list[tuple[uuid.UUID, dict[str, Any]]],
        reviewer: str,
    ) -> None:
        row = self.proposals.get(proposal_id)
        if row is None or row["status"] != "pending":
            raise MergeProposalAlreadyDecided(str(proposal_id))
        row["status"] = "approved"
        row["reviewer"] = reviewer
        row["decision"] = decision
        self.operations[proposal_id] = [
            {
                "sequence": index,
                "operation_type": "supersede_claim",
                "claim_candidate_id": claim_id,
                "operation_data": data,
            }
            for index, (claim_id, data) in enumerate(
                supersede_targets, start=1
            )
        ]


class FakeClaimRepository:
    """claim 확정 전이와 유효 구간 조회를 실 DB처럼 흉내 낸다.

    accepted는 불변이다. 같은 claim이 여러 번 실려도 확정은 한 번이므로,
    이미 accepted인 행은 세지 않고 건너뛴다.
    """

    def __init__(self) -> None:
        self.status: dict[uuid.UUID, str] = {}
        self.valid_from: dict[uuid.UUID, datetime | None] = {}
        self.calls: list[tuple[uuid.UUID, ...]] = []

    def add_claim(
        self,
        *,
        status: str = "pending",
        valid_from: datetime | None = EARLY,
    ) -> uuid.UUID:
        claim_id = uuid.uuid4()
        self.status[claim_id] = status
        self.valid_from[claim_id] = valid_from
        return claim_id

    def accept_claims(self, *, claim_ids: Any) -> int:
        self.calls.append(tuple(claim_ids))
        accepted = 0
        for claim_id in claim_ids:
            if self.status.get(claim_id, "pending") == "pending":
                self.status[claim_id] = "accepted"
                accepted += 1
        return accepted

    def get_claim_validity(
        self, *, claim_id: uuid.UUID
    ) -> tuple[str, datetime | None, datetime | None] | None:
        if claim_id not in self.status:
            return None
        return (self.status[claim_id], self.valid_from[claim_id], None)


@dataclass
class FakeUnitOfWork:
    """발행이 쓰는 transaction 경계를 대신한다.

    실 UoW는 재진입할 수 없다 — `with`에 다시 들어가면 새 session을 열고
    빠져나가며 rollback한다. 그 성질을 여기서도 지켜, 발행이 파생 서비스에
    자기 자신을 그대로 넘기면 테스트가 깨지게 한다.
    """

    committed: int = 0
    entered: int = 0
    depth: int = 0

    def __post_init__(self) -> None:
        self.artifacts = FakeArtifactRepository()
        self.knowledge_candidates = FakeClaimRepository()
        self.mutation_proposals = FakeMutationRepository()
        self.block_verdicts = FakeBlockVerdictRepository(
            self.artifacts.proposals
        )

    def __enter__(self) -> Self:
        if self.depth:
            raise AssertionError("UnitOfWork는 재진입할 수 없다")
        self.depth += 1
        self.entered += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.depth -= 1
        return None

    def commit(self) -> None:
        self.committed += 1


def _record_verdict(
    uow: FakeUnitOfWork,
    proposal_id: uuid.UUID,
    block_index: int,
    *,
    verdict: str = "approved",
    rejection_reason: str | None = None,
    chosen_winner_claim_id: uuid.UUID | None = None,
    block_hash: str | None = None,
) -> None:
    """블록 결정 한 줄을 저널에 미리 넣는다."""
    proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
    assert proposal is not None
    current = block_content_hash(proposal.blocks[block_index])
    uow.block_verdicts.upsert_verdict(
        proposal_id=proposal_id,
        block_index=block_index,
        block_content_hash=current if block_hash is None else block_hash,
        verdict=verdict,
        rejection_reason=rejection_reason,
        chosen_winner_claim_id=chosen_winner_claim_id,
        reviewer=REVIEWER,
        reviewed_at=DECIDED_AT,
    )


def _publish(
    uow: FakeUnitOfWork,
    proposal_id: uuid.UUID,
    *,
    base_revision_id: uuid.UUID | None = None,
):
    """발행을 같은 인자로 부르는 지름길이다."""
    return publish_artifact_proposal(
        uow,
        workspace_id=WORKSPACE_ID,
        proposal_id=proposal_id,
        base_revision_id=base_revision_id,
        reviewer=REVIEWER,
        now=DECIDED_AT,
    )


def test_partial_approval_publishes_only_approved_blocks() -> None:
    """5블록 중 하나를 반려하면 판에는 4블록만 오른다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    claim_ids = [claims.add_claim() for _ in range(5)]
    blocks = tuple(
        _claim_block(claim_id, f"predicate_{index}")
        for index, claim_id in enumerate(claim_ids)
    )
    artifact_id = uuid.uuid4()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id, blocks=blocks, base_revision_id=None
    )
    for index in range(5):
        _record_verdict(
            uow,
            proposal_id,
            index,
            verdict="rejected" if index == 2 else "approved",
            rejection_reason="근거가 약하다" if index == 2 else None,
        )

    result = _publish(uow, proposal_id)

    assert result.verdict == "approved"
    assert result.blocks_published == 4
    assert result.blocks_rejected == 1
    assert result.revision_id is not None
    assert result.revision_number == 1
    stored = uow.artifacts.revision_blocks(result.revision_id)
    assert [block.heading for block in stored] == [
        "predicate_0",
        "predicate_1",
        "predicate_3",
        "predicate_4",
    ]
    # 반려된 블록의 claim은 확정되지 않는다.
    assert claims.status[claim_ids[2]] == "pending"
    assert claim_ids[2] not in claims.calls[0]
    assert result.claims_accepted == 4
    assert uow.artifacts.proposals[proposal_id]["status"] == "approved"
    assert uow.committed == 1


def test_contested_winner_is_materialized_and_resolved() -> None:
    """다툼 블록은 승자 variant만 판에 남고 모순 결정이 파생된다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    winner = claims.add_claim(valid_from=LATER)
    loser = claims.add_claim(valid_from=EARLY)
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser)
    )
    block = _contested_block(
        heading="rate_limit_per_minute",
        contradiction_id=contradiction_id,
        first=winner,
        second=loser,
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=(block,), base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0, chosen_winner_claim_id=winner)

    result = _publish(uow, proposal_id)

    assert result.contradictions_resolved == 1
    assert result.revision_id is not None
    stored = uow.artifacts.revision_blocks(result.revision_id)
    assert len(stored) == 1
    published = stored[0]
    assert published.block_kind == BLOCK_KIND_CLAIM_SECTION
    assert published.heading == "rate_limit_per_minute"
    assert published.body == "60 (2026-07-20 관찰)"
    assert published.claim_ids == (winner,)
    assert published.proposal_ids == ()
    assert published.variants == ()
    assert published.ontology_version == "1"
    assert [source.claim_id for source in published.sources] == [winner]
    # 패자의 흔적은 판 어디에도 남지 않는다.
    assert loser not in published.claim_ids
    row = uow.mutation_proposals.proposals[contradiction_id]
    assert row["status"] == "approved"
    assert row["decision"]["winner_claim_id"] == str(winner)
    operations = uow.mutation_proposals.operations[contradiction_id]
    assert [op["claim_candidate_id"] for op in operations] == [loser]
    # 승자 claim은 발행이 확정한다.
    assert claims.status[winner] == "accepted"
    assert claims.status[loser] == "pending"
    assert result.claims_accepted == 1
    assert uow.committed == 1


def test_undecided_blocks_are_reported_with_their_indices() -> None:
    """결정이 빠진 블록이 있으면 그 번호를 함께 알린다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    blocks = tuple(
        _claim_block(claims.add_claim(), f"predicate_{index}")
        for index in range(3)
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 1)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "UNDECIDED_BLOCKS"
    assert error.value.undecided == (0, 2)
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


def test_changed_block_content_refuses_publish() -> None:
    """결정 당시 본 본문과 지금 본문이 다르면 발행하지 않는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    blocks = (_claim_block(claims.add_claim(), "release_month"),)
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0, block_hash="f" * 64)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "STALE_BLOCK"
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


def test_intervening_revision_refuses_publish() -> None:
    """검토 사이에 다른 판이 끼어들면 낙관 락이 막는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    artifact_id = uuid.uuid4()
    seed_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(_claim_block(claims.add_claim(), "옛 판"),),
        base_revision_id=None,
        status="approved",
    )
    base = uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=(_claim_block(claims.add_claim(), "옛 판"),),
        source_proposal_id=seed_id,
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(_claim_block(claims.add_claim(), "새 절"),),
        base_revision_id=base,
    )
    _record_verdict(uow, proposal_id, 0)
    uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=2,
        blocks=(_claim_block(claims.add_claim(), "끼어든 판"),),
        source_proposal_id=seed_id,
    )

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id, base_revision_id=base)

    assert error.value.code == "STALE_BASE"
    assert len(uow.artifacts.revisions) == 2
    assert uow.artifacts.proposals[proposal_id]["status"] == "pending"
    assert uow.committed == 0


def test_client_base_revision_mismatch_refuses_publish() -> None:
    """클라이언트가 본 기준 판이 변경안의 기준과 다르면 막는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(_claim_block(claims.add_claim(), "release_month"),),
        base_revision_id=None,
    )
    _record_verdict(uow, proposal_id, 0)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id, base_revision_id=uuid.uuid4())

    assert error.value.code == "STALE_BASE"
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


def test_revision_number_collision_maps_to_stale_base() -> None:
    """판 번호를 다른 승인이 선점하면 낡음으로 옮겨 담는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    artifact_id = uuid.uuid4()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(_claim_block(claims.add_claim(), "release_month"),),
        base_revision_id=None,
    )
    _record_verdict(uow, proposal_id, 0)
    # 최신 판 조회는 통과하되 쓰기에서 부딪히도록, 다른 문서로 조회를
    # 비켜 간 뒤 같은 번호를 선점해 둔다.
    uow.artifacts.revisions.append(
        {
            "id": uuid.uuid4(),
            "artifact_id": artifact_id,
            "revision_number": 1,
            "blocks": [],
            "source_proposal_id": proposal_id,
            "hidden": True,
        }
    )
    original = uow.artifacts.find_latest_revision_id_and_number

    def _blind(*, artifact_id: uuid.UUID) -> tuple[uuid.UUID, int] | None:
        """끼어든 판을 아직 보지 못한 순간을 흉내 낸다."""
        del artifact_id
        return None

    uow.artifacts.find_latest_revision_id_and_number = _blind  # type: ignore[method-assign]
    try:
        with pytest.raises(PublishError) as error:
            _publish(uow, proposal_id)
    finally:
        uow.artifacts.find_latest_revision_id_and_number = original  # type: ignore[method-assign]

    assert error.value.code == "STALE_BASE"
    assert uow.artifacts.proposals[proposal_id]["status"] == "pending"
    assert uow.committed == 0


def test_resolve_race_rolls_the_whole_publish_back() -> None:
    """파생 모순 결정이 경합에 지면 판도 남지 않는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    winner = claims.add_claim()
    loser = claims.add_claim()
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser), status="approved"
    )
    blocks = (
        _claim_block(claims.add_claim(), "release_month"),
        _contested_block(
            heading="rate_limit_per_minute",
            contradiction_id=contradiction_id,
            first=winner,
            second=loser,
        ),
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0)
    _record_verdict(uow, proposal_id, 1, chosen_winner_claim_id=winner)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "CONFLICT_RACE"
    assert uow.artifacts.revisions == []
    assert uow.artifacts.proposals[proposal_id]["status"] == "pending"
    assert claims.calls == []
    assert uow.committed == 0


def test_all_blocks_rejected_ends_as_rejection() -> None:
    """전 블록 반려는 판 없이 변경안을 반려로 끝맺는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    first = claims.add_claim()
    second = claims.add_claim()
    blocks = (
        _claim_block(first, "release_month"),
        _claim_block(second, "rate_limit"),
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(
        uow, proposal_id, 0, verdict="rejected", rejection_reason="근거 없음"
    )
    _record_verdict(
        uow, proposal_id, 1, verdict="rejected", rejection_reason="값이 틀렸다"
    )

    result = _publish(uow, proposal_id)

    assert result.verdict == "rejected"
    assert result.revision_id is None
    assert result.revision_number is None
    assert result.blocks_published == 0
    assert result.blocks_rejected == 2
    assert result.claims_accepted == 0
    row = uow.artifacts.proposals[proposal_id]
    assert row["status"] == "rejected"
    assert row["rejection_reason"] == "근거 없음; 값이 틀렸다"
    assert uow.artifacts.revisions == []
    assert claims.status[first] == "pending"
    assert claims.status[second] == "pending"
    assert uow.committed == 1


def test_counters_report_every_axis() -> None:
    """결과 카운터는 실린 블록·뺀 블록·파생 결정·확정 claim을 센다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    kept = claims.add_claim()
    dropped = claims.add_claim()
    already = claims.add_claim(status="accepted")
    winner = claims.add_claim(valid_from=LATER)
    loser = claims.add_claim(valid_from=EARLY)
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser)
    )
    blocks = (
        _claim_block(kept, "release_month"),
        _claim_block(already, "owner"),
        _claim_block(dropped, "rate_limit"),
        _contested_block(
            heading="timeout_seconds",
            contradiction_id=contradiction_id,
            first=winner,
            second=loser,
        ),
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0)
    _record_verdict(uow, proposal_id, 1)
    _record_verdict(
        uow, proposal_id, 2, verdict="rejected", rejection_reason="값이 낡았다"
    )
    _record_verdict(uow, proposal_id, 3, chosen_winner_claim_id=winner)

    result = _publish(uow, proposal_id)

    assert result.blocks_published == 3
    assert result.blocks_rejected == 1
    assert result.contradictions_resolved == 1
    # 이미 확정된 claim은 다시 세지 않는다.
    assert result.claims_accepted == 2
    assert claims.calls == [(kept, already, winner)]


def test_rejected_contested_block_never_resolves_its_contradiction() -> None:
    """반려된 다툼 블록의 승자 값은 발행이 무시한다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    kept = claims.add_claim()
    winner = claims.add_claim()
    loser = claims.add_claim()
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser)
    )
    blocks = (
        _claim_block(kept, "release_month"),
        _contested_block(
            heading="rate_limit_per_minute",
            contradiction_id=contradiction_id,
            first=winner,
            second=loser,
        ),
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0)
    # 저널에는 승자 값이 남아 있지만 결정은 반려다.
    _record_verdict(
        uow,
        proposal_id,
        1,
        verdict="rejected",
        rejection_reason="둘 다 근거가 약하다",
        chosen_winner_claim_id=winner,
    )

    result = _publish(uow, proposal_id)

    assert result.contradictions_resolved == 0
    assert result.blocks_published == 1
    assert uow.mutation_proposals.proposals[contradiction_id]["status"] == (
        "pending"
    )
    assert uow.mutation_proposals.operations[contradiction_id] == []
    assert claims.status[winner] == "pending"
    assert claims.status[loser] == "pending"
    assert result.claims_accepted == 1


def test_winner_outside_variants_is_refused_at_publish() -> None:
    """저널에 남은 승자가 후보 밖이면 발행 시점에도 거절한다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    winner = claims.add_claim()
    loser = claims.add_claim()
    stranger = claims.add_claim()
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser)
    )
    block = _contested_block(
        heading="rate_limit_per_minute",
        contradiction_id=contradiction_id,
        first=winner,
        second=loser,
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=(block,), base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0, chosen_winner_claim_id=stranger)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "INVALID"
    assert uow.artifacts.revisions == []
    assert uow.mutation_proposals.proposals[contradiction_id]["status"] == (
        "pending"
    )
    assert uow.committed == 0


def test_contested_approval_without_winner_is_refused() -> None:
    """다툼 블록 승인에 승자가 없으면 실체화할 것이 없다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    winner = claims.add_claim()
    loser = claims.add_claim()
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser)
    )
    block = _contested_block(
        heading="rate_limit_per_minute",
        contradiction_id=contradiction_id,
        first=winner,
        second=loser,
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=(block,), base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "INVALID"
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


@pytest.mark.parametrize("status", ["approved", "rejected", "abandoned"])
def test_decided_proposal_cannot_be_published(status: str) -> None:
    """결정이 끝난 변경안은 다시 발행하지 않는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(_claim_block(claims.add_claim(), "release_month"),),
        base_revision_id=None,
        status=status,
    )

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "ALREADY_DECIDED"
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


def test_unknown_proposal_is_refused() -> None:
    """없는 변경안은 발행할 수 없다."""
    uow = FakeUnitOfWork()

    with pytest.raises(PublishError) as error:
        _publish(uow, uuid.uuid4())

    assert error.value.code == "NOT_FOUND"
    assert uow.committed == 0


def test_blank_reviewer_is_refused() -> None:
    """발행자 없는 확정은 감사 기록이 되지 못한다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(_claim_block(claims.add_claim(), "release_month"),),
        base_revision_id=None,
    )
    _record_verdict(uow, proposal_id, 0)

    with pytest.raises(PublishError) as error:
        publish_artifact_proposal(
            uow,
            workspace_id=WORKSPACE_ID,
            proposal_id=proposal_id,
            base_revision_id=None,
            reviewer="   ",
            now=DECIDED_AT,
        )

    assert error.value.code == "INVALID"
    assert uow.committed == 0
