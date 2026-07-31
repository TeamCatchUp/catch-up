"""entity 요약 카드 Compiler를 fake 저장소로 확인한다.

fake는 DB 제약을 흉내 낸다. `(workspace, idempotency_key)` UNIQUE와
결정된 행의 되살리기 거부와 반려 사유 강제가 그것이다. 조용히 덮어쓰는
fake를 쓰면 멱등 규칙이 지켜지는지 이 테스트로 알 수 없기 때문이다.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import EntityCardSource
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    ARTIFACT_KIND_ENTITY_SUMMARY,
)
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_entity_artifacts,
)

NOW = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
WORKSPACE = 1

VOCABULARY = ExtractionVocabulary(
    snapshot_id="3",
    predicate_entries=(
        PredicateEntry(
            name="release_month",
            definition="배포 예정 월을 나타낸다.",
            value_type="date",
        ),
        PredicateEntry(
            name="rate_limit",
            definition="분당 허용 호출 수를 나타낸다.",
            value_type="number",
        ),
    ),
)


def _claim(
    *,
    node_id: uuid.UUID,
    predicate: str = "rate_limit",
    value: object = 60,
    value_type: str = "number",
    minutes: int = 0,
) -> StoredClaimCandidate:
    """canonical 노드를 subject로 삼는 claim 후보를 하나 만든다."""
    return StoredClaimCandidate(
        id=uuid.uuid4(),
        subject_entity_candidate_id=None,
        subject_node_id=node_id,
        subject_resolved_node_id=None,
        predicate=predicate,
        value_type=value_type,
        value=value,
        statement=f"{predicate}는 {value}이다",
        observed_at=NOW + timedelta(minutes=minutes),
    )


class FakeClaimRepository:
    def __init__(self, claims: list[StoredClaimCandidate]) -> None:
        self.claims = list(claims)

    def find_claim_candidates(self, *, workspace_id: int):
        del workspace_id
        return tuple(self.claims)


class FakeMutationProposalRepository:
    def __init__(
        self,
        pending: dict[uuid.UUID, list[StoredPendingProposal]] | None = None,
    ) -> None:
        self.pending = dict(pending or {})

    def find_pending_for_subject_node(
        self, *, workspace_id: int, node_id: uuid.UUID
    ) -> list[StoredPendingProposal]:
        assert workspace_id == WORKSPACE
        return list(self.pending.get(node_id, ()))


class FakeArtifactRepository:
    """artifact 저장소를 DB 제약까지 흉내 내어 대신한다.

    `(workspace_id, idempotency_key)` UNIQUE를 dict 키로 재현한다. 같은
    키의 행이 pending·abandoned면 되살리고, 사람이 결정한 approved·
    rejected면 `ArtifactProposalConflict`를 던진다. 반려에는 사유를
    강제하고, 근거 없는 블록은 저장 전에 막는다. 실 어댑터가 그렇게
    동작하기 때문이다.
    """

    def __init__(self, sources: list[EntityCardSource]) -> None:
        self.sources = list(sources)
        self.artifacts: dict[tuple[str, uuid.UUID], uuid.UUID] = {}
        self.titles: dict[uuid.UUID, str] = {}
        self.by_key: dict[str, dict] = {}
        self.by_id: dict[uuid.UUID, dict] = {}
        self.revisions: list[dict] = []

    def find_top_entity_nodes(self, *, limit: int) -> list[EntityCardSource]:
        return list(self.sources[:limit])

    def get_or_create_artifact(
        self, *, kind: str, subject_node_id: uuid.UUID, title: str
    ) -> uuid.UUID:
        found = self.artifacts.get((kind, subject_node_id))
        if found is not None:
            return found
        artifact_id = uuid.uuid4()
        self.artifacts[(kind, subject_node_id)] = artifact_id
        self.titles[artifact_id] = title
        return artifact_id

    def find_latest_revision_id_and_number(
        self, *, artifact_id: uuid.UUID
    ) -> tuple[uuid.UUID, int] | None:
        rows = [
            row
            for row in self.revisions
            if row["artifact_id"] == artifact_id
        ]
        if not rows:
            return None
        latest = max(rows, key=lambda row: row["revision_number"])
        return (latest["id"], latest["revision_number"])

    def find_latest_content_hashes(
        self, *, artifact_id: uuid.UUID
    ) -> set[str]:
        hashes: set[str] = set()
        rows = [
            row
            for row in self.revisions
            if row["artifact_id"] == artifact_id
        ]
        if rows:
            latest = max(rows, key=lambda row: row["revision_number"])
            source = self.by_id[latest["source_proposal_id"]]
            hashes.add(source["content_hash"])
        hashes.update(
            row["content_hash"]
            for row in self.by_key.values()
            if row["artifact_id"] == artifact_id
            and row["status"] in ("pending", "rejected")
        )
        return hashes

    def abandon_pending_proposals(self, *, artifact_id: uuid.UUID) -> int:
        abandoned = 0
        for row in self.by_key.values():
            if row["artifact_id"] == artifact_id and (
                row["status"] == "pending"
            ):
                row["status"] = "abandoned"
                abandoned += 1
        return abandoned

    def add_or_revive_proposal(
        self,
        *,
        artifact_id: uuid.UUID,
        blocks,
        content_hash: str,
        idempotency_key: str,
        base_revision_id: uuid.UUID | None,
    ) -> uuid.UUID:
        validate_blocks(blocks)
        existing = self.by_key.get(idempotency_key)
        if existing is not None:
            if existing["status"] not in ("pending", "abandoned"):
                raise ArtifactProposalConflict(
                    f"{existing['status']} 상태의 변경안이 같은 멱등 키를"
                    f" 쓰고 있다."
                )
            existing.update(
                artifact_id=artifact_id,
                blocks=tuple(blocks),
                status="pending",
                content_hash=content_hash,
                base_revision_id=base_revision_id,
                rejection_reason=None,
            )
            return existing["id"]

        proposal_id = uuid.uuid4()
        row = {
            "id": proposal_id,
            "artifact_id": artifact_id,
            "blocks": tuple(blocks),
            "status": "pending",
            "content_hash": content_hash,
            "idempotency_key": idempotency_key,
            "base_revision_id": base_revision_id,
            "rejection_reason": None,
        }
        self.by_key[idempotency_key] = row
        self.by_id[proposal_id] = row
        return proposal_id

    def _pending_row(self, proposal_id: uuid.UUID) -> dict:
        """계류 중인 행만 내준다.

        실 저장소는 `status = 'pending'`을 UPDATE 조건에 두어 이미 결정된
        행에는 결정을 싣지 않는다. fake가 덮어쓰면 그 규칙이 사라진다.
        """
        row = self.by_id.get(proposal_id)
        if row is None or row["status"] != "pending":
            raise ProposalAlreadyDecided(
                f"변경안 {proposal_id}는 계류 중이 아니다"
            )
        return row

    def mark_rejected(
        self, *, proposal_id: uuid.UUID, reviewer: str, reason: str
    ) -> None:
        if not reason:
            raise ValueError("반려에는 사유가 필요하다.")
        row = self._pending_row(proposal_id)
        row["status"] = "rejected"
        row["rejection_reason"] = reason
        row["reviewer"] = reviewer

    def mark_approved(self, *, proposal_id: uuid.UUID, reviewer: str) -> None:
        row = self._pending_row(proposal_id)
        row["status"] = "approved"
        row["reviewer"] = reviewer

    def add_revision(
        self,
        *,
        artifact_id: uuid.UUID,
        revision_number: int,
        blocks,
        source_proposal_id: uuid.UUID,
    ) -> uuid.UUID:
        revision_id = uuid.uuid4()
        self.revisions.append(
            {
                "id": revision_id,
                "artifact_id": artifact_id,
                "revision_number": revision_number,
                "blocks": serialize_blocks(blocks),
                "source_proposal_id": source_proposal_id,
            }
        )
        return revision_id

    def list_pending_proposals(self) -> list[StoredArtifactProposal]:
        nodes = {
            artifact_id: node_id
            for (_, node_id), artifact_id in self.artifacts.items()
        }
        return [
            StoredArtifactProposal(
                id=row["id"],
                artifact_id=row["artifact_id"],
                subject_node_id=nodes[row["artifact_id"]],
                title=self.titles[row["artifact_id"]],
                status=row["status"],
                blocks=row["blocks"],
                content_hash=row["content_hash"],
                base_revision_id=row["base_revision_id"],
                rejection_reason=row["rejection_reason"],
            )
            for row in self.by_key.values()
            if row["status"] == "pending"
        ]

    def pending_rows(self) -> list[dict]:
        """계류 중인 변경안 행을 돌려준다. 테스트가 상태를 볼 자리다."""
        return [
            row for row in self.by_key.values() if row["status"] == "pending"
        ]


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        sources: list[EntityCardSource],
        claims: list[StoredClaimCandidate],
        pending: dict[uuid.UUID, list[StoredPendingProposal]] | None = None,
    ) -> None:
        self.artifacts = FakeArtifactRepository(sources)
        self.knowledge_candidates = FakeClaimRepository(claims)
        self.mutation_proposals = FakeMutationProposalRepository(pending)
        self.committed = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed += 1


def _source(node_id: uuid.UUID, name: str = "결제 기능") -> EntityCardSource:
    return EntityCardSource(node_id=node_id, display_name=name, claim_count=1)


def _run(uow: FakeUnitOfWork, *, limit: int = 2):
    return compile_entity_artifacts(
        uow,
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
        limit=limit,
    )


def _only_pending(uow: FakeUnitOfWork) -> dict:
    rows = uow.artifacts.pending_rows()
    assert len(rows) == 1
    return rows[0]


def _publish(uow: FakeUnitOfWork, *, revision_number: int) -> uuid.UUID:
    """지금 계류 중인 변경안 하나를 승인해 판으로 발행한다."""
    proposal_id = _only_pending(uow)["id"]
    row = uow.artifacts.by_id[proposal_id]
    uow.artifacts.mark_approved(proposal_id=proposal_id, reviewer="tester")
    uow.artifacts.add_revision(
        artifact_id=row["artifact_id"],
        revision_number=revision_number,
        blocks=row["blocks"],
        source_proposal_id=proposal_id,
    )
    return proposal_id


def _contradiction(
    *,
    node_id: uuid.UUID,
    claim_ids: tuple[uuid.UUID, ...],
) -> StoredPendingProposal:
    """모순 계획서 한 건을 판정기가 남긴 형태 그대로 만든다."""
    return StoredPendingProposal(
        id=uuid.uuid4(),
        proposal_kind="contradiction",
        summary="'rate_limit' 값이 2종으로 갈린다: claim 2건",
        resolver_metadata={
            "subject_key": f"node:{node_id}",
            "predicate": "rate_limit",
            "values": [
                {
                    "claim_id": str(claim_ids[0]),
                    "value": 60,
                    "normalized": "60.0",
                    "observed_at": NOW.isoformat(),
                    "statement": "rate_limit는 60이다",
                },
                {
                    "claim_id": str(claim_ids[1]),
                    "value": 120,
                    "normalized": "120.0",
                    "observed_at": (NOW + timedelta(days=1)).isoformat(),
                    "statement": "rate_limit는 120이다",
                },
            ],
        },
    )


def test_entity_without_pending_proposal_gets_claim_sections_only() -> None:
    """계류 안건이 없으면 claim_section만 남고 열린 질문이 없다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[
            _claim(node_id=node_id, value=60),
            _claim(
                node_id=node_id,
                predicate="release_month",
                value="2026-09",
                value_type="date",
            ),
        ],
    )

    result = _run(uow)

    assert result.nodes_considered == 1
    assert result.proposals_created == 1
    assert result.proposals_revived == 0
    assert result.proposals_abandoned == 0
    assert result.unchanged_skipped == 0
    assert uow.committed == 1

    row = _only_pending(uow)
    blocks = row["blocks"]
    assert [block.block_kind for block in blocks] == [
        BLOCK_KIND_CLAIM_SECTION,
        BLOCK_KIND_CLAIM_SECTION,
    ]
    assert blocks[0].body == "2026-09 (2026-07-30 관찰)"
    assert blocks[0].ontology_version == "3"
    assert row["base_revision_id"] is None
    artifact_id = uow.artifacts.artifacts[
        (ARTIFACT_KIND_ENTITY_SUMMARY, node_id)
    ]
    assert row["artifact_id"] == artifact_id
    assert uow.artifacts.titles[artifact_id] == "결제 기능"


def test_predicate_order_follows_dictionary_then_name() -> None:
    """사전 등재 predicate가 사전 순서로 먼저, 미등재는 이름순으로 뒤에 온다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[
            _claim(node_id=node_id, predicate="zeta_note", value="뒤"),
            _claim(node_id=node_id, predicate="rate_limit", value=60),
            _claim(node_id=node_id, predicate="alpha_note", value="앞"),
            _claim(
                node_id=node_id,
                predicate="release_month",
                value="2026-09",
                value_type="date",
            ),
        ],
    )

    _run(uow)

    headings = [block.heading for block in _only_pending(uow)["blocks"]]
    assert headings == [
        "release_month",
        "rate_limit",
        "alpha_note",
        "zeta_note",
    ]


def test_multiple_values_are_all_listed_without_judgement() -> None:
    """값이 여럿이면 관찰 순서대로 전부 나열하고 고르지 않는다."""
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[newer, older],
    )

    _run(uow)

    block = _only_pending(uow)["blocks"][0]
    assert block.body == (
        "60 (2026-07-30 관찰)\n120 (2026-07-30 관찰)"
    )
    assert block.claim_ids == (older.id, newer.id)


def test_pending_proposal_becomes_open_question_block() -> None:
    """계류 안건은 값 후보를 그대로 나열한 열린 질문으로 실린다."""
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, newer.id))
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[older, newer],
        pending={node_id: [proposal]},
    )

    _run(uow)

    blocks = _only_pending(uow)["blocks"]
    question = blocks[-1]
    assert question.block_kind == BLOCK_KIND_OPEN_QUESTION
    assert question.heading == "열린 질문: contradiction"
    assert question.proposal_ids == (proposal.id,)
    assert question.body.splitlines() == [
        "'rate_limit' 값이 2종으로 갈린다: claim 2건",
        "- 60 (2026-07-30 관찰)",
        "- 120 (2026-07-31 관찰)",
    ]
    # 근거 claim도 함께 가리켜야 블록이 Read Set 노릇을 한다.
    assert question.claim_ids == (older.id, newer.id)
    # 모순이 있어도 claim_section은 값을 그대로 남긴다.
    assert blocks[0].block_kind == BLOCK_KIND_CLAIM_SECTION
    assert blocks[0].body.splitlines() == [
        "60 (2026-07-30 관찰)",
        "120 (2026-07-30 관찰)",
    ]


def test_duplicate_proposal_open_question_keeps_summary() -> None:
    """병합 안건은 요약을 각색 없이 그대로 싣는다."""
    node_id = uuid.uuid4()
    proposal = StoredPendingProposal(
        id=uuid.uuid4(),
        proposal_kind="duplicate",
        summary="같은 대상으로 보이는 후보 2건을 합칠지 묻는다",
        resolver_metadata={"member_ids": [str(uuid.uuid4())]},
    )
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[_claim(node_id=node_id)],
        pending={node_id: [proposal]},
    )

    _run(uow)

    question = _only_pending(uow)["blocks"][-1]
    assert question.heading == "열린 질문: duplicate"
    assert question.body == "같은 대상으로 보이는 후보 2건을 합칠지 묻는다"
    assert question.proposal_ids == (proposal.id,)


def test_recompiling_same_input_does_nothing() -> None:
    """같은 입력을 다시 컴파일하면 아무것도 쓰지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[_claim(node_id=node_id)],
    )
    _run(uow)
    first = _only_pending(uow)["id"]

    result = _run(uow)

    assert result.unchanged_skipped == 1
    assert result.proposals_created == 0
    assert result.proposals_revived == 0
    assert result.proposals_abandoned == 0
    assert _only_pending(uow)["id"] == first


def test_changed_claim_abandons_pending_and_writes_new() -> None:
    """claim 값이 달라지면 낡은 계류 변경안을 접고 새로 올린다."""
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[claim])
    _run(uow)
    stale_id = _only_pending(uow)["id"]

    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    result = _run(uow)

    assert result.proposals_abandoned == 1
    # 낡은 안건을 접고 그 자리를 대신했으므로 갱신으로 센다.
    assert result.proposals_revived == 1
    assert result.proposals_created == 0
    assert result.unchanged_skipped == 0
    fresh = _only_pending(uow)
    assert fresh["id"] != stale_id
    assert uow.artifacts.by_id[stale_id]["status"] == "abandoned"
    assert fresh["blocks"][0].body == "120 (2026-07-30 관찰)"


def test_returning_to_abandoned_content_revives_that_row() -> None:
    """접힌 내용으로 되돌아오면 같은 행을 되살린다."""
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[claim])
    _run(uow)
    original_id = _only_pending(uow)["id"]

    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    _run(uow)
    uow.knowledge_candidates.claims = [claim]
    result = _run(uow)

    assert result.proposals_revived == 1
    assert result.proposals_created == 0
    assert result.proposals_abandoned == 1
    assert _only_pending(uow)["id"] == original_id


def test_rejected_content_is_not_proposed_again() -> None:
    """사람이 반려한 내용과 지문이 같으면 다시 올리지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[_claim(node_id=node_id)],
    )
    _run(uow)
    proposal_id = _only_pending(uow)["id"]
    uow.artifacts.mark_rejected(
        proposal_id=proposal_id,
        reviewer="tester",
        reason="근거가 부족하다",
    )

    result = _run(uow)

    assert result.unchanged_skipped == 1
    assert result.proposals_created == 0
    assert result.proposals_revived == 0
    assert uow.artifacts.pending_rows() == []
    assert uow.artifacts.by_id[proposal_id]["status"] == "rejected"


def test_base_revision_points_at_latest_revision() -> None:
    """새 변경안은 지금 발행된 최신 판을 딛고 선다."""
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[claim])
    _run(uow)
    approved_id = _only_pending(uow)["id"]
    artifact_id = uow.artifacts.by_id[approved_id]["artifact_id"]
    uow.artifacts.mark_approved(proposal_id=approved_id, reviewer="tester")
    revision_id = uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=uow.artifacts.by_id[approved_id]["blocks"],
        source_proposal_id=approved_id,
    )

    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    result = _run(uow)

    assert result.proposals_created == 1
    assert _only_pending(uow)["base_revision_id"] == revision_id


def test_approved_content_is_skipped_before_conflict() -> None:
    """승인으로 발행된 내용은 지문 검사에서 먼저 걸러진다.

    걸러지지 않으면 `add_or_revive_proposal`이 승인 행과 같은 멱등 키를
    만나 예외를 던진다. 이 테스트는 그 예외가 나지 않음을 확인한다.
    """
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[claim])
    _run(uow)
    approved_id = _only_pending(uow)["id"]
    artifact_id = uow.artifacts.by_id[approved_id]["artifact_id"]
    uow.artifacts.mark_approved(proposal_id=approved_id, reviewer="tester")
    uow.artifacts.add_revision(
        artifact_id=artifact_id,
        revision_number=1,
        blocks=uow.artifacts.by_id[approved_id]["blocks"],
        source_proposal_id=approved_id,
    )

    result = _run(uow)

    assert result.unchanged_skipped == 1
    assert result.proposals_created == 0


def test_node_without_claims_is_considered_but_not_written() -> None:
    """쓸 내용이 없는 노드는 세기만 하고 빈 문서를 만들지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[])

    result = _run(uow)

    assert result.nodes_considered == 1
    assert result.proposals_created == 0
    assert uow.artifacts.by_key == {}


def test_limit_bounds_the_nodes_read() -> None:
    """limit이 이번 실행이 볼 노드 수를 정한다."""
    first = uuid.uuid4()
    second = uuid.uuid4()
    uow = FakeUnitOfWork(
        sources=[_source(first, "첫 기능"), _source(second, "둘째 기능")],
        claims=[_claim(node_id=first), _claim(node_id=second)],
    )

    result = _run(uow, limit=1)

    assert result.nodes_considered == 1
    assert result.proposals_created == 1


def test_claims_via_resolved_candidate_are_attributed_to_node() -> None:
    """후보를 거쳐 해소된 claim도 그 노드의 카드에 실린다."""
    node_id = uuid.uuid4()
    claim = StoredClaimCandidate(
        id=uuid.uuid4(),
        subject_entity_candidate_id=uuid.uuid4(),
        subject_node_id=None,
        subject_resolved_node_id=node_id,
        predicate="rate_limit",
        value_type="number",
        value=60,
        statement="rate_limit는 60이다",
        observed_at=NOW,
    )
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[claim])

    _run(uow)

    block = _only_pending(uow)["blocks"][0]
    assert block.claim_ids == (claim.id,)


def test_blocks_are_deterministic_across_input_order() -> None:
    """입력 순서가 달라도 블록과 지문이 같아야 한다."""
    node_id = uuid.uuid4()
    claims = [
        _claim(node_id=node_id, value=60, minutes=0),
        _claim(node_id=node_id, value=120, minutes=30),
        _claim(
            node_id=node_id,
            predicate="release_month",
            value="2026-09",
            value_type="date",
        ),
    ]
    forward = FakeUnitOfWork(sources=[_source(node_id)], claims=claims)
    backward = FakeUnitOfWork(
        sources=[_source(node_id)], claims=list(reversed(claims))
    )

    _run(forward)
    _run(backward)

    assert (
        _only_pending(forward)["content_hash"]
        == _only_pending(backward)["content_hash"]
    )
    assert _only_pending(forward)["blocks"] == _only_pending(backward)[
        "blocks"
    ]


def test_written_blocks_hold_their_own_hash() -> None:
    """저장된 지문이 저장된 블록에서 다시 계산된 값과 같다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        sources=[_source(node_id)],
        claims=[_claim(node_id=node_id)],
    )

    _run(uow)

    row = _only_pending(uow)
    assert row["content_hash"] == blocks_content_hash(row["blocks"])


def test_conflicting_revert_skips_only_that_node() -> None:
    """승인된 옛 판 내용으로 되돌아간 노드만 건너뛰고 나머지는 돈다.

    rev1=A와 rev2=B가 이미 발행된 뒤 내용이 A로 돌아오면 멱등 키가
    승인 행과 부딪힌다. 그 노드 하나만 접어 두고 다른 노드의 카드
    작업은 그대로 끝나야 한다.
    """
    first = uuid.uuid4()
    second = uuid.uuid4()
    claim = _claim(node_id=first, value=60)
    uow = FakeUnitOfWork(
        sources=[_source(first, "첫 기능"), _source(second, "둘째 기능")],
        claims=[claim],
    )
    _run(uow, limit=1)
    _publish(uow, revision_number=1)
    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    _run(uow, limit=1)
    _publish(uow, revision_number=2)

    uow.knowledge_candidates.claims = [claim, _claim(node_id=second)]
    result = _run(uow, limit=2)

    assert result.nodes_considered == 2
    assert result.proposals_conflicted == 1
    assert result.proposals_created == 1
    assert uow.committed == 3
    row = _only_pending(uow)
    artifact_id = uow.artifacts.artifacts[
        (ARTIFACT_KIND_ENTITY_SUMMARY, second)
    ]
    assert row["artifact_id"] == artifact_id


def test_skipped_node_abandons_stale_pending() -> None:
    """지문이 그대로라 넘기는 노드도 내용이 다른 낡은 계류는 접는다."""
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(sources=[_source(node_id)], claims=[claim])
    _run(uow)
    _publish(uow, revision_number=1)
    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    _run(uow)
    stale_id = _only_pending(uow)["id"]

    uow.knowledge_candidates.claims = [claim]
    result = _run(uow)

    assert result.unchanged_skipped == 1
    assert result.proposals_abandoned == 1
    assert result.proposals_created == 0
    assert result.proposals_revived == 0
    assert uow.artifacts.by_id[stale_id]["status"] == "abandoned"
    assert uow.artifacts.pending_rows() == []


def test_fake_refuses_to_revive_decided_rows() -> None:
    """fake가 결정된 행의 되살리기를 실 DB처럼 거절한다."""
    repository = FakeArtifactRepository([])
    artifact_id = uuid.uuid4()
    blocks = (
        ArtifactBlock(
            block_kind=BLOCK_KIND_CLAIM_SECTION,
            heading="rate_limit",
            body="60",
            claim_ids=(uuid.uuid4(),),
            proposal_ids=(),
            ontology_version="3",
        ),
    )
    proposal_id = repository.add_or_revive_proposal(
        artifact_id=artifact_id,
        blocks=blocks,
        content_hash="hash",
        idempotency_key="key",
        base_revision_id=None,
    )
    repository.mark_rejected(
        proposal_id=proposal_id, reviewer="tester", reason="근거가 부족하다"
    )

    with pytest.raises(ArtifactProposalConflict):
        repository.add_or_revive_proposal(
            artifact_id=artifact_id,
            blocks=blocks,
            content_hash="hash",
            idempotency_key="key",
            base_revision_id=None,
        )
