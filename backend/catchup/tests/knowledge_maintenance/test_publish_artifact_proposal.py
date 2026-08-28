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
from structlog.testing import capture_logs

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
    CODE_NOT_FOUND,
)
from catchup.knowledge_maintenance.services.publish_artifact_proposal import (
    CODE_STALE_BASE,
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
        self, *, proposal_id: uuid.UUID, for_update: bool = False
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

    def find_latest_revision_blocks(
        self, *, artifact_id: uuid.UUID
    ) -> tuple[ArtifactBlock, ...] | None:
        latest = self.find_latest_revision_id_and_number(
            artifact_id=artifact_id
        )
        if latest is None:
            return None
        return self.revision_blocks(latest[0])

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

    def insert_verdict_if_absent(
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
    ) -> bool:
        """이미 결정이 있는 블록은 건드리지 않는다."""
        if (proposal_id, block_index) in self.verdicts:
            return False
        self.upsert_verdict(
            proposal_id=proposal_id,
            block_index=block_index,
            block_content_hash=block_content_hash,
            verdict=verdict,
            rejection_reason=rejection_reason,
            chosen_winner_claim_id=chosen_winner_claim_id,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        return True

    def delete_verdict(
        self, *, proposal_id: uuid.UUID, block_index: int
    ) -> bool:
        """결정 한 줄을 지운다. 없던 줄이면 False다."""
        if proposal_id not in self._proposals:
            raise ValueError(f"변경안 {proposal_id}가 없다")
        return self.verdicts.pop((proposal_id, block_index), None) is not None

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
            and self._is_decided(row["proposal_id"])
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

    def _is_decided(self, proposal_id: uuid.UUID) -> bool:
        """변경안이 사람의 결정으로 끝난 상태인지 본다."""
        row = self._proposals.get(proposal_id)
        return row is not None and row["status"] in ("approved", "rejected")


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
    undecided: str | None = None,
    rejection_reason: str | None = None,
):
    """발행을 같은 인자로 부르는 지름길이다."""
    return publish_artifact_proposal(
        uow,
        workspace_id=WORKSPACE_ID,
        proposal_id=proposal_id,
        base_revision_id=base_revision_id,
        reviewer=REVIEWER,
        undecided=undecided,
        rejection_reason=rejection_reason,
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

    assert error.value.code == "STALE_BASE_REVISION"
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

    assert error.value.code == "STALE_BASE_REVISION"
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

    assert error.value.code == "STALE_BASE_REVISION"
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


def test_rollback_log_names_the_resolved_contradictions() -> None:
    """앞선 파생 결정이 되감기면 무엇이 되감겼는지 로그로 남긴다.

    파생 서비스는 바깥 commit보다 먼저 자기 로그를 남긴다. 뒤이어 발행이
    엎어지면 감사 스트림에 해소 기록만 남으므로, 되감김 기록이 그 짝을
    맞춰 주어야 한다.
    """
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    first_winner = claims.add_claim(valid_from=LATER)
    first_loser = claims.add_claim(valid_from=EARLY)
    second_winner = claims.add_claim()
    second_loser = claims.add_claim()
    live_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(first_winner, first_loser)
    )
    # 둘째 안건은 이미 다른 판정이 끝내 두었다.
    decided_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(second_winner, second_loser), status="approved"
    )
    blocks = (
        _contested_block(
            heading="rate_limit_per_minute",
            contradiction_id=live_id,
            first=first_winner,
            second=first_loser,
        ),
        _contested_block(
            heading="timeout_seconds",
            contradiction_id=decided_id,
            first=second_winner,
            second=second_loser,
        ),
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0, chosen_winner_claim_id=first_winner)
    _record_verdict(uow, proposal_id, 1, chosen_winner_claim_id=second_winner)

    with capture_logs() as logs:
        with pytest.raises(PublishError) as error:
            _publish(uow, proposal_id)

    assert error.value.code == "CONFLICT_RACE"
    entries = [
        entry
        for entry in logs
        if entry["event"] == "artifact_publish_rolled_back"
    ]
    assert len(entries) == 1
    assert entries[0]["log_level"] == "warning"
    assert entries[0]["code"] == "CONFLICT_RACE"
    assert entries[0]["proposal_id"] == str(proposal_id)
    assert entries[0]["rolled_back_contradiction_ids"] == [str(live_id)]
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


def test_rollback_log_is_absent_on_success() -> None:
    """발행이 끝까지 가면 되감김 기록은 남지 않는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=(_claim_block(claims.add_claim(), "release_month"),),
        base_revision_id=None,
    )
    _record_verdict(uow, proposal_id, 0)

    with capture_logs() as logs:
        _publish(uow, proposal_id)

    events = [entry["event"] for entry in logs]
    assert "artifact_publish_rolled_back" not in events
    assert "artifact_proposal_published" in events


def test_variant_citing_a_foreign_claim_is_refused() -> None:
    """실체화한 승자가 남의 claim을 인용하면 근거 계약이 막는다.

    조립본은 승자 claim 하나만 근거로 남기므로, variant가 다른 후보의
    인용을 달고 있으면 sources가 claim_ids를 벗어난다. 그 문장은 문서에
    실릴 수 없다.
    """
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
    # 승자 후보가 패자의 인용을 달고 있다.
    poisoned = ArtifactBlock(
        block_kind=block.block_kind,
        heading=block.heading,
        body=block.body,
        claim_ids=block.claim_ids,
        proposal_ids=block.proposal_ids,
        ontology_version=block.ontology_version,
        sources=block.sources,
        variants=(
            ContestedVariant(
                claim_id=winner,
                body=block.variants[0].body,
                sources=(_source(loser, "남의 근거"),),
            ),
            block.variants[1],
        ),
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=(poisoned,), base_revision_id=None
    )
    _record_verdict(uow, proposal_id, 0, chosen_winner_claim_id=winner)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id)

    assert error.value.code == "INVALID"
    assert uow.artifacts.revisions == []
    # 조립은 쓰기 전에 끝나므로 파생 결정도 나가지 않는다.
    assert uow.mutation_proposals.proposals[contradiction_id]["status"] == (
        "pending"
    )
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

    assert error.value.code == "PROPOSAL_NOT_FOUND"
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


def test_error_codes_renamed() -> None:
    """낡음·없음 코드는 다른 라우트와 같은 이름 하나로 통일돼 있다."""
    assert CODE_STALE_BASE == "STALE_BASE_REVISION"
    assert CODE_NOT_FOUND == "PROPOSAL_NOT_FOUND"


def test_undecided_approve_records_verdicts_and_publishes() -> None:
    """미판정 블록에 approved 결정이 기록되고 그대로 발행된다.

    이미 있던 반려 결정은 그대로 남는다. 사람이 내린 결정을 일괄 승인이
    덮으면 안 되기 때문이다.
    """
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    blocks = tuple(
        _claim_block(claims.add_claim(), f"predicate_{index}")
        for index in range(3)
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )
    _record_verdict(
        uow,
        proposal_id,
        1,
        verdict="rejected",
        rejection_reason="근거가 약하다",
    )

    result = _publish(uow, proposal_id, undecided="approve")

    stored = uow.block_verdicts.list_for_proposal(proposal_id=proposal_id)
    assert [(row.block_index, row.verdict) for row in stored] == [
        (0, "approved"),
        (1, "rejected"),
        (2, "approved"),
    ]
    assert stored[0].reviewer == REVIEWER
    assert stored[2].reviewer == REVIEWER
    assert stored[1].rejection_reason == "근거가 약하다"
    assert result.blocks_published == 2
    assert result.blocks_rejected == 1


def test_undecided_approve_refuses_when_contested_block_is_undecided() -> None:
    """다툼 블록은 승자를 골라야 하므로 일괄 승인이 대신 결정하지 않는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    winner = claims.add_claim()
    loser = claims.add_claim()
    contradiction_id = uow.mutation_proposals.add_contradiction(
        claim_ids=(winner, loser)
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

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id, undecided="approve")

    assert error.value.code == "UNDECIDED_BLOCKS"
    assert error.value.undecided == (1,)
    assert uow.block_verdicts.verdicts == {}
    assert uow.artifacts.revisions == []
    assert uow.committed == 0


def test_undecided_reject_requires_reason_and_rejects_rest() -> None:
    """일괄 반려는 사유가 있어야 하고, 남은 블록을 모두 반려로 끝맺는다."""
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    blocks = tuple(
        _claim_block(claims.add_claim(), f"predicate_{index}")
        for index in range(2)
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id, undecided="reject")

    assert error.value.code == "INVALID"
    assert uow.block_verdicts.verdicts == {}

    result = _publish(
        uow,
        proposal_id,
        undecided="reject",
        rejection_reason="이번 판에는 싣지 않는다",
    )

    stored = uow.block_verdicts.list_for_proposal(proposal_id=proposal_id)
    assert [(row.block_index, row.verdict) for row in stored] == [
        (0, "rejected"),
        (1, "rejected"),
    ]
    assert all(
        row.rejection_reason == "이번 판에는 싣지 않는다" for row in stored
    )
    assert result.verdict == "rejected"
    assert result.revision_id is None
    assert result.blocks_published == 0
    assert result.blocks_rejected == 2


def test_bulk_undecided_never_overwrites_a_concurrent_human_verdict() -> None:
    """미결정 목록을 읽은 뒤 들어온 사람의 판정이 그대로 살아남는다.

    일괄 승인은 결정 목록을 먼저 읽어 빈 블록을 고른다. 그 사이에 다른
    검토자가 같은 블록에 반려를 저장하면, 일괄 쓰기가 그 반려를 덮어써서는
    안 된다. 저장소의 첫 목록 조회 직후 사람의 반려를 끼워 넣어 그 틈을
    그대로 만든다.
    """
    uow = FakeUnitOfWork()
    claims = uow.knowledge_candidates
    blocks = tuple(
        _claim_block(claims.add_claim(), f"predicate_{index}")
        for index in range(3)
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(), blocks=blocks, base_revision_id=None
    )

    verdicts = uow.block_verdicts
    original_list = verdicts.list_for_proposal
    interleaved: list[int] = []

    def list_then_interleave(
        *, proposal_id: uuid.UUID
    ) -> tuple[StoredBlockVerdict, ...]:
        rows = original_list(proposal_id=proposal_id)
        if not interleaved:
            interleaved.append(1)
            verdicts.upsert_verdict(
                proposal_id=proposal_id,
                block_index=1,
                block_content_hash=block_content_hash(blocks[1]),
                verdict="rejected",
                rejection_reason="사람이 직접 반려했다",
                chosen_winner_claim_id=None,
                reviewer="user:other",
                reviewed_at=DECIDED_AT,
            )
        return rows

    verdicts.list_for_proposal = list_then_interleave

    result = _publish(uow, proposal_id, undecided="approve")

    human = verdicts.verdicts[(proposal_id, 1)]
    assert human["verdict"] == "rejected"
    assert human["reviewer"] == "user:other"
    assert human["rejection_reason"] == "사람이 직접 반려했다"
    # 발행은 실제로 저장된 결정으로 진행된다. 사람이 반려한 블록 하나가
    # 반려로 세어진다.
    assert result.verdict == "approved"
    assert result.blocks_published == 2
    assert result.blocks_rejected == 1


def _seed_modified_document(
    uow: FakeUnitOfWork,
) -> tuple[uuid.UUID, uuid.UUID, tuple[ArtifactBlock, ...]]:
    """발행판 하나를 세우고 그 위에 블록 하나만 고친 변경안을 올린다.

    발행판과 변경안은 첫 블록을 바이트 그대로 공유하고 둘째 블록만 본문이
    다르다. 검토 화면이라면 둘째 블록만 변경으로 보인다.
    """
    claims = uow.knowledge_candidates
    artifact_id = uuid.uuid4()
    kept = _claim_block(claims.add_claim(), "predicate_0")
    old = _claim_block(claims.add_claim(), "predicate_1")
    seed_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(kept, old),
        base_revision_id=None,
        status="approved",
    )
    base = uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=(kept, old),
        source_proposal_id=seed_id,
    )
    changed = ArtifactBlock(
        block_kind=BLOCK_KIND_CLAIM_SECTION,
        heading="predicate_1",
        body="predicate_1 본문을 고쳤다",
        claim_ids=old.claim_ids,
        proposal_ids=(),
        ontology_version="1",
        sources=old.sources,
    )
    blocks = (kept, changed)
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=blocks,
        base_revision_id=base,
    )
    return base, proposal_id, blocks


def test_unchanged_block_needs_no_verdict_to_publish() -> None:
    """바뀌지 않은 블록은 결정이 없어도 발행을 막지 않는다.

    검토 화면은 발행판과 다른 블록만 보여 준다. 화면에 뜨지 않은 블록에
    결정을 요구하면 검토자가 발행할 길이 없다. 면제는 완전성 검사에서만
    하고, 결정 저널에는 아무것도 적지 않는다.
    """
    uow = FakeUnitOfWork()
    base, proposal_id, blocks = _seed_modified_document(uow)
    _record_verdict(uow, proposal_id, 1)

    result = _publish(uow, proposal_id, base_revision_id=base)

    assert result.verdict == "approved"
    assert result.blocks_published == 2
    assert result.blocks_rejected == 0
    assert result.revision_number == 2
    assert result.revision_id is not None
    stored = uow.artifacts.revision_blocks(result.revision_id)
    assert [block.heading for block in stored] == [
        "predicate_0",
        "predicate_1",
    ]
    assert stored[0].body == blocks[0].body
    assert stored[1].body == "predicate_1 본문을 고쳤다"
    # 면제는 자동 승인이 아니다. 사람이 결정하지 않은 블록에는 결정 행이
    # 생기지 않는다.
    assert (proposal_id, 0) not in uow.block_verdicts.verdicts


def test_human_rejection_on_an_unchanged_block_still_drops_it() -> None:
    """사람이 미변경 블록을 반려했으면 그 블록은 새 판에서 빠진다."""
    uow = FakeUnitOfWork()
    base, proposal_id, _ = _seed_modified_document(uow)
    _record_verdict(
        uow,
        proposal_id,
        0,
        verdict="rejected",
        rejection_reason="이 절은 더 이상 맞지 않는다",
    )
    _record_verdict(uow, proposal_id, 1)

    result = _publish(uow, proposal_id, base_revision_id=base)

    assert result.blocks_published == 1
    assert result.blocks_rejected == 1
    assert result.revision_id is not None
    stored = uow.artifacts.revision_blocks(result.revision_id)
    assert [block.heading for block in stored] == ["predicate_1"]


def test_bulk_undecided_skips_unchanged_blocks() -> None:
    """일괄 처리는 화면에 변경으로 보인 블록에만 결정을 만든다.

    일괄 반려가 미변경 블록까지 훑으면 검토자가 보지도 않은 내용이 문서
    에서 떨어진다.
    """
    uow = FakeUnitOfWork()
    base, proposal_id, _ = _seed_modified_document(uow)

    result = _publish(
        uow,
        proposal_id,
        base_revision_id=base,
        undecided="reject",
        rejection_reason="이번 판에는 싣지 않는다",
    )

    assert (proposal_id, 0) not in uow.block_verdicts.verdicts
    rejected = uow.block_verdicts.verdicts[(proposal_id, 1)]
    assert rejected["verdict"] == "rejected"
    # 미변경 블록은 결정 없이 그대로 실리고, 바뀐 블록만 반려로 빠진다.
    assert result.verdict == "approved"
    assert result.blocks_published == 1
    assert result.blocks_rejected == 1
    assert result.revision_id is not None
    stored = uow.artifacts.revision_blocks(result.revision_id)
    assert [block.heading for block in stored] == ["predicate_0"]


def test_stale_verdict_on_an_unchanged_block_refuses_publish() -> None:
    """미변경 블록에 남은 결정의 지문이 어긋나면 그대로 STALE_BLOCK이다."""
    uow = FakeUnitOfWork()
    base, proposal_id, _ = _seed_modified_document(uow)
    _record_verdict(uow, proposal_id, 0, block_hash="f" * 64)
    _record_verdict(uow, proposal_id, 1)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id, base_revision_id=base)

    assert error.value.code == "STALE_BLOCK"
    assert len(uow.artifacts.revisions) == 1
    assert uow.committed == 0


def _seed_evidence_swapped_document(
    uow: FakeUnitOfWork,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """발행판 하나를 세우고 근거만 갈아 끼운 변경안을 올린다.

    변경안의 둘째 블록은 발행판 블록과 종류·제목·본문·산문이 모두 같고
    가리키는 claim만 새 claim으로 바뀐다. 사람이 보지 않은 근거가 판에
    실릴 수 있는 자리라 발행이 결정을 요구해야 한다.
    """
    claims = uow.knowledge_candidates
    artifact_id = uuid.uuid4()
    kept = _claim_block(claims.add_claim(), "predicate_0")
    old = _claim_block(claims.add_claim(), "predicate_1")
    seed_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(kept, old),
        base_revision_id=None,
        status="approved",
    )
    base = uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=(kept, old),
        source_proposal_id=seed_id,
    )
    fresh_claim = claims.add_claim()
    swapped = _claim_block(fresh_claim, "predicate_1")
    assert swapped.body == old.body
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=(kept, swapped),
        base_revision_id=base,
    )
    return base, proposal_id, fresh_claim


def test_evidence_swap_without_verdict_refuses_publish() -> None:
    """본문이 같아도 근거가 갈린 블록은 결정 없이 실을 수 없다."""
    uow = FakeUnitOfWork()
    base, proposal_id, fresh_claim = _seed_evidence_swapped_document(uow)

    with pytest.raises(PublishError) as error:
        _publish(uow, proposal_id, base_revision_id=base)

    assert error.value.code == "UNDECIDED_BLOCKS"
    assert error.value.undecided == (1,)
    # 거절이므로 새 claim은 확정되지 않는다.
    assert uow.knowledge_candidates.status[fresh_claim] != "accepted"
    assert len(uow.artifacts.revisions) == 1
    assert uow.committed == 0


def test_evidence_swap_publishes_once_a_human_approves_it() -> None:
    """근거가 갈린 블록도 사람이 승인하면 실리고 새 claim이 확정된다."""
    uow = FakeUnitOfWork()
    base, proposal_id, fresh_claim = _seed_evidence_swapped_document(uow)
    _record_verdict(uow, proposal_id, 1)

    result = _publish(uow, proposal_id, base_revision_id=base)

    assert result.verdict == "approved"
    assert result.blocks_published == 2
    assert uow.knowledge_candidates.status[fresh_claim] == "accepted"
    assert result.revision_id is not None
    stored = uow.artifacts.revision_blocks(result.revision_id)
    assert stored[1].claim_ids == (fresh_claim,)
