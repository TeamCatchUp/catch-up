"""문서 변경안의 승인·반려 판정을 fake 저장소 위에서 확인한다.

fake는 실 DB의 제약을 흉내 낸다. 반려에 사유가 없으면 막고, 같은 판
번호를 두 번 쓰면 막고, 블록은 JSONB처럼 직렬화해 담았다가 되돌린다.
제약을 흉내 내지 않는 fake는 서비스가 조용히 어긴 규칙을 통과시킨다.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    ProposalReviewError,
)
from catchup.knowledge_maintenance.services.review_artifact_proposal import (
    review_artifact_proposal,
)

REVIEWER = "tester"


def _blocks(body: str) -> tuple[ArtifactBlock, ...]:
    """근거를 갖춘 블록 한 벌을 만든다."""
    return (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="release_month",
            body=body,
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="1",
        ),
    )


class FakeArtifactRepository:
    """artifact 저장소를 DB 제약까지 흉내 내어 대신한다.

    블록은 실 DB처럼 직렬화한 형태로 담았다가 읽을 때 되돌린다. 그래야
    저장된 판이 변경안과 같은 객체를 공유하지 않는 것이 드러난다.

    `status <> 'rejected' OR rejection_reason IS NOT NULL` CHECK과
    `(artifact_id, revision_number)` UNIQUE를 그대로 재현한다. 조용히
    통과시키면 서비스가 규칙을 어겨도 테스트가 초록으로 남는다.

    결정 쓰기가 계류 행에만 걸리는 낙관적 전이도 재현한다. 실 저장소는
    `status = 'pending'`을 UPDATE 조건에 두고 바뀐 행이 없으면 던지는데,
    덮어쓰는 fake는 결정이 겹쳐 쓰이는 것을 그대로 통과시킨다.
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
        )

    def find_latest_revision_id_and_number(
        self,
        *,
        artifact_id: uuid.UUID,
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
                raise ValueError("같은 판 번호가 이미 있다")
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

    def revision_blocks(self, revision_id: uuid.UUID):
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

    def mark_approved(
        self,
        *,
        proposal_id: uuid.UUID,
        reviewer: str,
    ) -> None:
        row = self._pending_row(proposal_id)
        row["status"] = "approved"
        row["reviewer"] = reviewer

    def mark_rejected(
        self,
        *,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        if reason is None:
            raise ValueError("반려는 사유가 있어야 한다")
        row = self._pending_row(proposal_id)
        row["status"] = "rejected"
        row["reviewer"] = reviewer
        row["rejection_reason"] = reason


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.artifacts = FakeArtifactRepository()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed = True


def test_approve_creates_first_revision() -> None:
    """첫 승인은 1번 판을 만들고 변경안을 승인으로 끝맺는다."""
    uow = FakeUnitOfWork()
    artifact_id = uuid.uuid4()
    blocks = _blocks("2026-09")
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=blocks,
        base_revision_id=None,
    )

    result = review_artifact_proposal(
        uow,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer=REVIEWER,
    )

    assert result.proposal_id == proposal_id
    assert result.verdict == "approved"
    assert result.revision_number == 1
    assert result.revision_id is not None
    assert uow.artifacts.proposals[proposal_id]["status"] == "approved"
    assert uow.artifacts.proposals[proposal_id]["reviewer"] == REVIEWER
    assert uow.committed is True


def test_approve_freezes_proposal_blocks_into_revision() -> None:
    """저장된 판은 변경안과 내용이 같되 같은 객체를 공유하지 않는다."""
    uow = FakeUnitOfWork()
    artifact_id = uuid.uuid4()
    blocks = _blocks("2026-09")
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=blocks,
        base_revision_id=None,
    )

    result = review_artifact_proposal(
        uow,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer=REVIEWER,
    )

    assert result.revision_id is not None
    stored = uow.artifacts.revision_blocks(result.revision_id)
    proposal = uow.artifacts.get_proposal(proposal_id=proposal_id)
    assert proposal is not None
    assert stored == proposal.blocks
    assert stored is not proposal.blocks
    assert stored[0] is not proposal.blocks[0]


def test_approve_increments_revision_number() -> None:
    """이미 판이 있으면 다음 번호로 쌓는다."""
    uow = FakeUnitOfWork()
    artifact_id = uuid.uuid4()
    seed_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=_blocks("옛 판"),
        base_revision_id=None,
        status="approved",
    )
    first_revision = uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=_blocks("옛 판"),
        source_proposal_id=seed_id,
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=_blocks("새 판"),
        base_revision_id=first_revision,
    )

    result = review_artifact_proposal(
        uow,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer=REVIEWER,
    )

    assert result.revision_number == 2
    assert len(uow.artifacts.revisions) == 2


def test_approve_refuses_stale_base_revision() -> None:
    """딛고 선 판이 최신이 아니면 승인하지 않는다."""
    uow = FakeUnitOfWork()
    artifact_id = uuid.uuid4()
    seed_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=_blocks("옛 판"),
        base_revision_id=None,
        status="approved",
    )
    stale_base = uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=_blocks("옛 판"),
        source_proposal_id=seed_id,
    )
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=_blocks("낡은 근거 위의 변경안"),
        base_revision_id=stale_base,
    )
    # 검토 사이에 다른 승인이 새 판을 끼워 넣는다.
    uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=2,
        blocks=_blocks("끼어든 판"),
        source_proposal_id=seed_id,
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=REVIEWER,
        )

    assert len(uow.artifacts.revisions) == 2
    assert uow.artifacts.proposals[proposal_id]["status"] == "pending"
    assert uow.committed is False


def test_approve_refuses_first_revision_when_base_is_missing() -> None:
    """판이 없는데 딛고 선 판을 가리키면 승인하지 않는다."""
    uow = FakeUnitOfWork()
    artifact_id = uuid.uuid4()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=_blocks("2026-09"),
        base_revision_id=uuid.uuid4(),
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=REVIEWER,
        )

    assert uow.artifacts.revisions == []


def test_reject_records_reason() -> None:
    """반려는 사유와 함께 남고 판을 만들지 않는다."""
    uow = FakeUnitOfWork()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=_blocks("2026-09"),
        base_revision_id=None,
    )

    result = review_artifact_proposal(
        uow,
        proposal_id=proposal_id,
        verdict="rejected",
        reviewer=REVIEWER,
        reason="근거가 부족하다",
    )

    assert result.verdict == "rejected"
    assert result.revision_id is None
    assert result.revision_number is None
    row = uow.artifacts.proposals[proposal_id]
    assert row["status"] == "rejected"
    assert row["rejection_reason"] == "근거가 부족하다"
    assert uow.artifacts.revisions == []
    assert uow.committed is True


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reject_without_reason_is_refused(reason: str | None) -> None:
    """사유 없는 반려는 막는다. 빈 문자열도 사유가 아니다."""
    uow = FakeUnitOfWork()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=_blocks("2026-09"),
        base_revision_id=None,
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer=REVIEWER,
            reason=reason,
        )

    assert uow.artifacts.proposals[proposal_id]["status"] == "pending"
    assert uow.committed is False


@pytest.mark.parametrize("status", ["approved", "rejected", "abandoned"])
def test_already_decided_proposal_cannot_be_reviewed(status: str) -> None:
    """결정이 끝난 변경안은 다시 판정하지 않는다. 조용히 넘기지도 않는다."""
    uow = FakeUnitOfWork()
    artifact_id = uuid.uuid4()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=artifact_id,
        blocks=_blocks("2026-09"),
        base_revision_id=None,
        status=status,
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict="approved",
            reviewer=REVIEWER,
        )

    assert uow.artifacts.revisions == []
    assert uow.artifacts.proposals[proposal_id]["status"] == status
    assert uow.committed is False


@pytest.mark.parametrize("status", ["approved", "rejected", "abandoned"])
def test_marking_decided_proposal_is_refused_by_repository(
    status: str,
) -> None:
    """이미 결정된 행에는 저장소가 결정을 싣지 않는다.

    서비스의 계류 검사를 거치지 않고 저장소를 직접 부른다. 그 검사는
    잠금 없는 읽기라 두 검토가 나란히 통과할 수 있으므로, 마지막 방어는
    쓰기 자체에 있어야 한다.
    """
    repository = FakeArtifactRepository()
    proposal_id = repository.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=_blocks("2026-09"),
        base_revision_id=None,
        status=status,
    )

    with pytest.raises(ProposalAlreadyDecided):
        repository.mark_approved(proposal_id=proposal_id, reviewer=REVIEWER)
    with pytest.raises(ProposalAlreadyDecided):
        repository.mark_rejected(
            proposal_id=proposal_id,
            reviewer=REVIEWER,
            reason="근거가 부족하다",
        )

    assert repository.proposals[proposal_id]["status"] == status
    assert repository.proposals[proposal_id]["reviewer"] is None


def test_unknown_proposal_is_refused() -> None:
    """없는 변경안은 판정할 수 없다."""
    uow = FakeUnitOfWork()

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=uuid.uuid4(),
            verdict="approved",
            reviewer=REVIEWER,
        )

    assert uow.committed is False


def test_unknown_verdict_is_refused() -> None:
    """승인도 반려도 아닌 판정은 받지 않는다."""
    uow = FakeUnitOfWork()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=_blocks("2026-09"),
        base_revision_id=None,
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict="maybe",
            reviewer=REVIEWER,
        )

    assert uow.artifacts.proposals[proposal_id]["status"] == "pending"
    assert uow.committed is False


def test_blank_reviewer_is_refused() -> None:
    """검토자 없는 결정은 감사 기록이 되지 않으므로 막는다."""
    uow = FakeUnitOfWork()
    proposal_id = uow.artifacts.add_proposal(
        artifact_id=uuid.uuid4(),
        blocks=_blocks("2026-09"),
        base_revision_id=None,
    )

    with pytest.raises(ProposalReviewError):
        review_artifact_proposal(
            uow,
            proposal_id=proposal_id,
            verdict="approved",
            reviewer="  ",
        )

    assert uow.artifacts.revisions == []
    assert uow.committed is False
