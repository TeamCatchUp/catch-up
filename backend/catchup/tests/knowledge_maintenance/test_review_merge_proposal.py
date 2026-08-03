"""병합 안건 결정 서비스의 규칙을 fake 저장소로 확인한다.

결정은 pending에서만 가능하고, 반려에는 사유가 필수이며, 이미 결정된
행은 어떤 경로로도 되살아나지 않는다. fake는 실 DB의 전이 규칙을
그대로 흉내 내야 한다 — 실물과 다른 관대함은 버그를 숨긴다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from types import TracebackType
from typing import Any
from typing import Self

import pytest

from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredMergeCandidate
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredMergeProposal
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    MergeReviewError,
)
from catchup.knowledge_maintenance.services.review_merge_proposal import (
    review_merge_proposal,
)

WORKSPACE_ID = 1


@dataclass
class FakeMergeProposalRepository:
    """결정 전이 규칙을 실 DB처럼 흉내 낸다."""

    rows: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)

    def add_row(self, *, status: str = "pending", **overrides: Any) -> uuid.UUID:
        proposal_id = uuid.uuid4()
        row: dict[str, Any] = {
            "id": proposal_id,
            "status": status,
            "proposal_kind": "duplicate",
            "summary": "같은 이름 후보 병합",
            "resolver_metadata": {"reason": "judge same"},
            "idempotency_key": f"merge:{uuid.uuid4().hex}",
            "reviewer": None,
            "reviewed_at": None,
            "rejection_reason": None,
            "applied_at": None,
            "candidates": (),
        }
        row.update(overrides)
        self.rows[proposal_id] = row
        return proposal_id

    def list_pending_duplicates(
        self, *, workspace_id: int
    ) -> list[StoredMergeProposal]:
        return [
            StoredMergeProposal(
                id=row["id"],
                summary=row["summary"],
                resolver_metadata=row["resolver_metadata"],
                candidates=row["candidates"],
            )
            for row in self.rows.values()
            if row["status"] == "pending"
            and row["proposal_kind"] == "duplicate"
        ]

    def mark_merge_approved(
        self, *, workspace_id: int, proposal_id: uuid.UUID, reviewer: str
    ) -> None:
        self._decide(proposal_id, status="approved", reviewer=reviewer)

    def mark_merge_rejected(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        if not reason:
            raise AssertionError("DB CHECK: 반려에는 사유가 있어야 한다")
        self._decide(
            proposal_id,
            status="rejected",
            reviewer=reviewer,
            rejection_reason=reason,
        )

    def _decide(self, proposal_id: uuid.UUID, **values: Any) -> None:
        row = self.rows.get(proposal_id)
        if (
            row is None
            or row["status"] != "pending"
            or row["proposal_kind"] != "duplicate"
        ):
            raise MergeProposalAlreadyDecided(str(proposal_id))
        row.update(values)
        row["reviewed_at"] = "now"

    def revive_or_skip(self, proposal_id: uuid.UUID) -> uuid.UUID:
        """add_duplicate_proposal의 upsert 경로를 축약해 흉내 낸다."""
        row = self.rows[proposal_id]
        if row["status"] in ("approved", "applied", "rejected"):
            return proposal_id
        row["status"] = "pending"
        row["reviewer"] = None
        row["reviewed_at"] = None
        row["rejection_reason"] = None
        row["applied_at"] = None
        return proposal_id


@dataclass
class FakeUnitOfWork:
    mutation_proposals: FakeMergeProposalRepository
    committed: int = 0

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
        self.committed += 1


def _uow() -> FakeUnitOfWork:
    return FakeUnitOfWork(mutation_proposals=FakeMergeProposalRepository())


def test_approve_records_decision() -> None:
    uow = _uow()
    proposal_id = uow.mutation_proposals.add_row()

    result = review_merge_proposal(
        uow,
        workspace_id=WORKSPACE_ID,
        proposal_id=proposal_id,
        verdict="approved",
        reviewer="ba2slk",
    )

    row = uow.mutation_proposals.rows[proposal_id]
    assert result.verdict == "approved"
    assert row["status"] == "approved"
    assert row["reviewer"] == "ba2slk"
    assert row["reviewed_at"] is not None
    assert uow.committed == 1


def test_reject_requires_reason() -> None:
    uow = _uow()
    proposal_id = uow.mutation_proposals.add_row()

    with pytest.raises(MergeReviewError):
        review_merge_proposal(
            uow,
            workspace_id=WORKSPACE_ID,
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer="ba2slk",
            reason="   ",
        )
    assert uow.mutation_proposals.rows[proposal_id]["status"] == "pending"


def test_reject_records_reason() -> None:
    uow = _uow()
    proposal_id = uow.mutation_proposals.add_row()

    result = review_merge_proposal(
        uow,
        workspace_id=WORKSPACE_ID,
        proposal_id=proposal_id,
        verdict="rejected",
        reviewer="ba2slk",
        reason="다른 팀이다",
    )

    row = uow.mutation_proposals.rows[proposal_id]
    assert result.verdict == "rejected"
    assert row["status"] == "rejected"
    assert row["rejection_reason"] == "다른 팀이다"


def test_double_decision_is_refused() -> None:
    uow = _uow()
    proposal_id = uow.mutation_proposals.add_row(status="approved")

    with pytest.raises(MergeReviewError):
        review_merge_proposal(
            uow,
            workspace_id=WORKSPACE_ID,
            proposal_id=proposal_id,
            verdict="rejected",
            reviewer="ba2slk",
            reason="번복 시도",
        )
    assert uow.mutation_proposals.rows[proposal_id]["status"] == "approved"


def test_unknown_verdict_is_refused() -> None:
    uow = _uow()
    proposal_id = uow.mutation_proposals.add_row()

    with pytest.raises(MergeReviewError):
        review_merge_proposal(
            uow,
            workspace_id=WORKSPACE_ID,
            proposal_id=proposal_id,
            verdict="hold",
            reviewer="ba2slk",
        )


def test_missing_proposal_is_refused() -> None:
    uow = _uow()

    with pytest.raises(MergeReviewError):
        review_merge_proposal(
            uow,
            workspace_id=WORKSPACE_ID,
            proposal_id=uuid.uuid4(),
            verdict="approved",
            reviewer="ba2slk",
        )


def test_revive_resets_decision_fields() -> None:
    repository = FakeMergeProposalRepository()
    proposal_id = repository.add_row(
        status="abandoned", reviewer="ghost", rejection_reason="옛 사유"
    )

    repository.revive_or_skip(proposal_id)

    row = repository.rows[proposal_id]
    assert row["status"] == "pending"
    assert row["reviewer"] is None
    assert row["reviewed_at"] is None
    assert row["rejection_reason"] is None
    assert row["applied_at"] is None


def test_decided_row_is_not_revived() -> None:
    repository = FakeMergeProposalRepository()
    proposal_id = repository.add_row(status="rejected", reviewer="ba2slk")

    repository.revive_or_skip(proposal_id)

    row = repository.rows[proposal_id]
    assert row["status"] == "rejected"
    assert row["reviewer"] == "ba2slk"


def test_list_pending_renders_candidates() -> None:
    repository = FakeMergeProposalRepository()
    candidate = StoredMergeCandidate(
        id=uuid.uuid4(),
        proposed_name="SSO 로그인",
        proposed_type="feature",
        resolution_status="pending",
    )
    repository.add_row(candidates=(candidate,))
    repository.add_row(status="approved")

    listed = repository.list_pending_duplicates(workspace_id=WORKSPACE_ID)

    assert len(listed) == 1
    assert listed[0].candidates == (candidate,)
