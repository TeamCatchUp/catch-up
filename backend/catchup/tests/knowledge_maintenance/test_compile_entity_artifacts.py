"""문서 Compiler의 본문 조립과 검토 큐 규칙을 fake 저장소로 확인한다.

정의 하나를 세워 두고 그 아래에서 본문이 어떻게 서는지만 본다. 정의
순회 자체(정의가 여럿일 때의 차례, 깨진 정의 격리, 관계 절)는
`test_compile_definition_artifacts.py`가 맡는다.

fake는 DB 제약을 흉내 낸다. `(workspace, idempotency_key)` UNIQUE와
결정된 행의 되살리기 거부와 반려 사유 강제가 그것이다. 조용히 덮어쓰는
fake를 쓰면 멱등 규칙이 지켜지는지 이 테스트로 알 수 없기 때문이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import pytest

from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CLAIM_SECTION
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_OPEN_QUESTION
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import blocks_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import EntityCardSource
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_definition_artifacts,
)
from catchup.tests.knowledge_maintenance.test_artifact_definition_repository import (
    FakeArtifactDefinitionRepository,
)

NOW = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
WORKSPACE = 1

# 노드 원장 한 줄이다. (node_id, display_name, entity_type,
# lifecycle_state) 넷으로, 정의가 고르는 질의가 이 줄을 본다.
_NodeRow = tuple[uuid.UUID, str, str, str]

ENTITY_TYPE = "feature"
DEFINITION_KIND = "entity_summary"
DEFINITION_ID = uuid.UUID("00000000-0000-4000-8000-0000000000d1")
CHANNEL_ID = uuid.UUID("00000000-0000-4000-8000-0000000000c1")

# 이 파일이 세우는 정의 하나의 선택 규칙이다. 절을 고르지 않으므로
# claim 절의 차례는 사전이 정한 그대로가 되고, 관계 경로가 없으므로
# 본문은 claim과 계류 안건만으로 선다.
SELECTION_SPEC: dict[str, Any] = {
    "entity_filter": {"entity_types": [ENTITY_TYPE]},
    "relation_paths": [],
    "predicate_sections": None,
}

VOCABULARY = ExtractionVocabulary(
    snapshot_id="3",
    entity_type_entries=(
        EntityTypeEntry(
            name=ENTITY_TYPE,
            definition="제품이 제공하는 기능이다.",
            identity_scope="standalone",
        ),
    ),
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
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    citation_verified: bool | None = None,
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
        valid_from=valid_from,
        valid_to=valid_to,
        citation_verified=citation_verified,
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

    def __init__(
        self,
        nodes: list[tuple[uuid.UUID, str, str, str]] | None = None,
    ) -> None:
        # 정의로 고르는 질의가 보는 노드 원장이다. 한 줄은
        # (node_id, display_name, entity_type, lifecycle_state)다.
        self.nodes = list(nodes or ())
        # 정의에 매인 문서는 (정의, 대상)으로 하나다. 실 DB의 UNIQUE와
        # 같은 키를 dict 키로 재현한다.
        self.definition_artifacts: dict[
            tuple[uuid.UUID, uuid.UUID], uuid.UUID
        ] = {}
        # 문서 행에 실제로 적히는 칸들이다. 정의·채널·kind가 함께
        # 남는지 시험이 볼 자리가 있어야 한다.
        self.artifact_rows: dict[uuid.UUID, dict] = {}
        self.subjects: dict[uuid.UUID, uuid.UUID] = {}
        self.titles: dict[uuid.UUID, str] = {}
        self.by_key: dict[str, dict] = {}
        self.by_id: dict[uuid.UUID, dict] = {}
        self.revisions: list[dict] = []

    def find_entity_nodes_by_types(
        self, *, entity_types: Sequence[str]
    ) -> list[EntityCardSource]:
        # 실 어댑터와 같은 규칙으로 고르고 줄을 세운다. 종류가 맞고 살아
        # 있는 노드만 보며, 이름이 같으면 식별자를 문자열로 갈라 낸다.
        wanted = set(entity_types)
        matched = [
            (display_name, str(node_id), node_id)
            for node_id, display_name, entity_type, lifecycle_state in (
                self.nodes
            )
            if entity_type in wanted and lifecycle_state == "active"
        ]
        return [
            EntityCardSource(node_id=node_id, display_name=display_name)
            for display_name, _, node_id in sorted(
                matched, key=lambda row: (row[0], row[1])
            )
        ]

    def get_or_create_definition_artifact(
        self,
        *,
        definition_id: uuid.UUID,
        channel_id: uuid.UUID,
        kind: str,
        subject_node_id: uuid.UUID,
        title: str,
        folder_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """정의가 대상에 만드는 문서를 찾거나 새로 만든다.

        실 저장소와 같이 (정의, 대상)으로만 찾고, 이미 있으면 제목도
        폴더도 덮어쓰지 않는다.
        """
        found = self.definition_artifacts.get((definition_id, subject_node_id))
        if found is not None:
            return found
        artifact_id = uuid.uuid4()
        self.definition_artifacts[(definition_id, subject_node_id)] = (
            artifact_id
        )
        self._remember(
            artifact_id,
            definition_id=definition_id,
            channel_id=channel_id,
            kind=kind,
            subject_node_id=subject_node_id,
            title=title,
            folder_id=folder_id,
        )
        return artifact_id

    def find_definition_artifact(
        self,
        *,
        definition_id: uuid.UUID,
        subject_node_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """정의가 대상에 만든 문서를 찾기만 한다. 없으면 None이다."""
        return self.definition_artifacts.get(
            (definition_id, subject_node_id)
        )

    def _remember(
        self,
        artifact_id: uuid.UUID,
        *,
        definition_id: uuid.UUID | None,
        channel_id: uuid.UUID | None,
        kind: str,
        subject_node_id: uuid.UUID,
        title: str,
        folder_id: uuid.UUID | None = None,
    ) -> None:
        """새로 만든 문서 행의 칸들을 적어 둔다."""
        self.artifact_rows[artifact_id] = {
            "id": artifact_id,
            "definition_id": definition_id,
            "channel_id": channel_id,
            "kind": kind,
            "subject_node_id": subject_node_id,
            "title": title,
            "folder_id": folder_id,
        }
        self.subjects[artifact_id] = subject_node_id
        self.titles[artifact_id] = title

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

    def list_reusable_narratives(
        self, *, artifact_id: uuid.UUID
    ) -> dict[str, str]:
        """최신 판과 계류 변경안의 산문을 블록 지문으로 모은다.

        실 저장소와 같은 재료만 본다 — 발행된 최신 판 하나와 pending
        변경안이다. 반려·접힌 행은 빼야 사람이 반려한 산문이 되살아나지
        않는다.
        """
        found: dict[str, str] = {}
        rows = [
            row
            for row in self.revisions
            if row["artifact_id"] == artifact_id
        ]
        if rows:
            latest = max(rows, key=lambda row: row["revision_number"])
            for block in deserialize_blocks(latest["blocks"]):
                if block.narrative is not None:
                    found[block_content_hash(block)] = block.narrative
        for row in self.by_key.values():
            if row["artifact_id"] != artifact_id:
                continue
            if row["status"] != "pending":
                continue
            for block in row["blocks"]:
                if block.narrative is not None:
                    found[block_content_hash(block)] = block.narrative
        return found

    def abandon_pending_proposals(
        self,
        *,
        artifact_id: uuid.UUID,
        except_content_hash: str | None = None,
    ) -> int:
        abandoned = 0
        for row in self.by_key.values():
            if row["artifact_id"] == artifact_id and (
                row["status"] == "pending"
            ) and (
                except_content_hash is None
                or row["content_hash"] != except_content_hash
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
            # 실 DB의 기본값과 같다. Compiler가 만든 안건은 compiled다.
            "origin": "compiled",
            "created_at": NOW,
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

    def list_pending_proposals(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StoredArtifactProposal]:
        nodes = self.subjects
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
                origin=row["origin"],
                created_at=row["created_at"],
            )
            for row in self.by_key.values()
            if row["status"] == "pending"
        ]

    def pending_rows(self) -> list[dict]:
        """계류 중인 변경안 행을 돌려준다. 테스트가 상태를 볼 자리다."""
        return [
            row for row in self.by_key.values() if row["status"] == "pending"
        ]


class FakeBlockVerdictRepository:
    """블록 결정 저장소를 DB 제약까지 흉내 내어 대신한다.

    `(proposal_id, block_index)` UNIQUE를 dict 키로 재현하고, verdict 값과
    반려 사유와 결정자 공백 CHECK도 그대로 막는다. 변경안 저장 dict를
    artifact fake와 나눠 써서, 실 저장소처럼 변경안 FK를 거쳐 문서에
    닿는다. 그래야 남의 문서 반려가 섞이지 않는 것이 드러난다.
    """

    def __init__(self, proposals: dict[uuid.UUID, dict]) -> None:
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
        """결정이 매달린 변경안을 거쳐 문서를 찾는다."""
        row = self._proposals.get(proposal_id)
        return None if row is None else row["artifact_id"]


class NoRelationRepository:
    """관계를 묻는 순간 터지는 저장소다.

    이 파일의 정의는 관계 경로를 하나도 갖지 않는다. 그래도 조용한 빈
    저장소를 두면 경로가 실수로 들어왔을 때 관계 절이 없는 이유를
    알 수 없으므로, 물어보는 것 자체를 실패로 드러낸다.
    """

    def find_edges(self, **kwargs: object) -> list[object]:
        raise AssertionError("이 시험의 정의에는 관계 경로가 없다.")


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        nodes: list[_NodeRow],
        claims: list[StoredClaimCandidate],
        pending: dict[uuid.UUID, list[StoredPendingProposal]] | None = None,
    ) -> None:
        self.artifacts = FakeArtifactRepository(nodes=nodes)
        self.artifact_definitions = FakeArtifactDefinitionRepository(
            [(DEFINITION_ID, CHANNEL_ID, DEFINITION_KIND, SELECTION_SPEC)]
        )
        self.knowledge_candidates = FakeClaimRepository(claims)
        self.mutation_proposals = FakeMutationProposalRepository(pending)
        self.block_verdicts = FakeBlockVerdictRepository(self.artifacts.by_id)
        self.relations = NoRelationRepository()
        self.committed = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed += 1


def _node(node_id: uuid.UUID, name: str = "결제 기능") -> _NodeRow:
    """정의가 고를 수 있는 살아 있는 노드 한 줄을 만든다."""
    return (node_id, name, ENTITY_TYPE, "active")


def _title(name: str = "결제 기능") -> str:
    """정의가 그 이름의 노드에 지을 문서 제목을 만든다."""
    return f"{DEFINITION_KIND}: {name}"


def _run(uow: FakeUnitOfWork):
    return compile_definition_artifacts(
        uow,
        workspace_id=WORKSPACE,
        vocabulary=VOCABULARY,
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


def _reject_block(
    uow: FakeUnitOfWork,
    *,
    proposal_id: uuid.UUID,
    block_index: int,
    reason: str = "근거가 부족하다",
) -> str:
    """계류 변경안의 블록 하나에 반려 결정을 남기고 그 지문을 돌려준다."""
    block = uow.artifacts.by_id[proposal_id]["blocks"][block_index]
    digest = block_content_hash(block)
    uow.block_verdicts.upsert_verdict(
        proposal_id=proposal_id,
        block_index=block_index,
        block_content_hash=digest,
        verdict="rejected",
        rejection_reason=reason,
        chosen_winner_claim_id=None,
        reviewer="tester",
        reviewed_at=NOW,
    )
    return digest


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
        nodes=[_node(node_id)],
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
    artifact_id = uow.artifacts.definition_artifacts[(DEFINITION_ID, node_id)]
    assert row["artifact_id"] == artifact_id
    assert uow.artifacts.titles[artifact_id] == _title()


def test_predicate_order_follows_dictionary_then_name() -> None:
    """사전 등재 predicate가 사전 순서로 먼저, 미등재는 이름순으로 뒤에 온다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
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
        nodes=[_node(node_id)],
        claims=[newer, older],
    )

    _run(uow)

    block = _only_pending(uow)["blocks"][0]
    assert block.body == (
        "60 (2026-07-30 관찰)\n120 (2026-07-30 관찰)"
    )
    assert block.claim_ids == (older.id, newer.id)


def test_contradiction_predicate_renders_contested_block() -> None:
    """모순 안건이 걸린 predicate는 대조 블록 하나로 실린다."""
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, newer.id))
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [proposal]},
    )

    _run(uow)

    blocks = _only_pending(uow)["blocks"]
    assert [block.block_kind for block in blocks] == [BLOCK_KIND_CONTESTED]
    block = blocks[0]
    assert block.heading == "rate_limit"
    assert block.body == "상충하는 값 2개 — 검토 필요"
    assert block.proposal_ids == (proposal.id,)
    assert set(block.claim_ids) == {older.id, newer.id}
    # 후보 순서는 claim_id 사전순으로 고정한다. 관찰 시각이나 값으로 줄을
    # 세우면 컴파일러가 어느 값을 앞세울지 판단하는 셈이 된다.
    assert [variant.claim_id for variant in block.variants] == sorted(
        (older.id, newer.id), key=str
    )
    bodies = {
        variant.claim_id: variant.body for variant in block.variants
    }
    assert bodies[older.id] == "60 (2026-07-30 관찰)"
    assert bodies[newer.id] == "120 (2026-07-30 관찰)"
    for variant in block.variants:
        assert [source.claim_id for source in variant.sources] == [
            variant.claim_id
        ]
    validate_blocks(blocks)


def test_contested_block_replaces_its_open_question() -> None:
    """대조로 실린 모순 안건은 열린 질문으로 다시 나오지 않는다."""
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    contradiction = _contradiction(
        node_id=node_id, claim_ids=(older.id, newer.id)
    )
    duplicate = StoredPendingProposal(
        id=uuid.uuid4(),
        proposal_kind="duplicate",
        summary="같은 대상으로 보이는 후보 2건을 합칠지 묻는다",
        resolver_metadata={"member_ids": [str(uuid.uuid4())]},
    )
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [contradiction, duplicate]},
    )

    _run(uow)

    blocks = _only_pending(uow)["blocks"]
    assert [block.block_kind for block in blocks] == [
        BLOCK_KIND_CONTESTED,
        BLOCK_KIND_OPEN_QUESTION,
    ]
    # 모순이 아닌 안건은 열린 질문 그대로 남는다.
    assert blocks[1].proposal_ids == (duplicate.id,)
    proposal_ids = {
        proposal_id
        for block in blocks
        for proposal_id in block.proposal_ids
    }
    assert proposal_ids == {contradiction.id, duplicate.id}


def test_contested_variants_stay_inside_the_proposal() -> None:
    """안건이 다루지 않는 값은 후보가 아니라 따로 선 절로 실린다.

    후보를 절 전체로 넓히면 검토자가 안건 밖의 claim을 승자로 고를 수
    있게 되는데, 결정을 적용하는 쪽은 패자를 "안건의 claim - 승자"로
    본다. 그러면 고른 승자가 어디에도 속하지 않는다.
    """
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    unrelated = _claim(node_id=node_id, value=240, minutes=60)
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, newer.id))
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer, unrelated],
        pending={node_id: [proposal]},
    )

    _run(uow)

    blocks = _only_pending(uow)["blocks"]
    assert [block.block_kind for block in blocks] == [
        BLOCK_KIND_CONTESTED,
        BLOCK_KIND_CLAIM_SECTION,
    ]
    contested, section = blocks
    assert [variant.claim_id for variant in contested.variants] == sorted(
        (older.id, newer.id), key=str
    )
    assert set(contested.claim_ids) == {older.id, newer.id}
    assert contested.body == "상충하는 값 2개 — 검토 필요"
    # 안건 밖의 값은 같은 제목의 절로 뒤에 붙는다.
    assert section.heading == "rate_limit"
    assert section.claim_ids == (unrelated.id,)
    assert section.body == "240 (2026-07-30 관찰)"
    validate_blocks(blocks)


def test_contested_blocks_are_deterministic_across_input_order() -> None:
    """대조 블록도 입력 순서와 무관하게 같은 지문을 낸다."""
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, newer.id))
    forward = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [proposal]},
    )
    backward = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[newer, older],
        pending={node_id: [proposal]},
    )

    _run(forward)
    _run(backward)

    assert (
        _only_pending(forward)["content_hash"]
        == _only_pending(backward)["content_hash"]
    )
    # 같은 입력을 다시 컴파일해도 지문이 흔들리지 않아야 한다.
    assert _run(forward).unchanged_skipped == 1


def test_single_live_claim_keeps_open_question() -> None:
    """모순 안건이라도 살아 있는 값이 하나뿐이면 대조하지 않는다.

    대조는 후보가 둘 이상일 때만 성립한다. 한쪽이 닫힌 뒤에도 안건이
    열려 있으면 절은 평범한 claim_section으로 두고 질문만 남긴다.
    """
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    closed = _claim(
        node_id=node_id,
        value=120,
        minutes=30,
        valid_to=NOW + timedelta(days=1),
    )
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, closed.id))
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, closed],
        pending={node_id: [proposal]},
    )

    _run(uow)

    blocks = _only_pending(uow)["blocks"]
    assert [block.block_kind for block in blocks] == [
        BLOCK_KIND_CLAIM_SECTION,
        BLOCK_KIND_OPEN_QUESTION,
    ]
    question = blocks[-1]
    assert question.heading == "열린 질문: contradiction"
    assert question.body.splitlines() == [
        "'rate_limit' 값이 2종으로 갈린다: claim 2건",
        "- 60 (2026-07-30 관찰)",
        "- 120 (2026-07-31 관찰)",
    ]
    # 근거 claim도 함께 가리켜야 블록이 Read Set 노릇을 한다.
    assert question.claim_ids == (older.id, closed.id)


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
        nodes=[_node(node_id)],
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
        nodes=[_node(node_id)],
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
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
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
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
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
        nodes=[_node(node_id)],
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
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
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
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
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
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[])

    result = _run(uow)

    assert result.nodes_considered == 1
    assert result.proposals_created == 0
    assert uow.artifacts.by_key == {}


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
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])

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
    forward = FakeUnitOfWork(nodes=[_node(node_id)], claims=claims)
    backward = FakeUnitOfWork(
        nodes=[_node(node_id)], claims=list(reversed(claims))
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
        nodes=[_node(node_id)],
        claims=[_claim(node_id=node_id)],
    )

    _run(uow)

    row = _only_pending(uow)
    assert row["content_hash"] == blocks_content_hash(row["blocks"])


def test_approved_revert_becomes_new_review_event() -> None:
    """승인된 옛 판 내용으로 되돌아오면 새 판 기준의 검토 사건이 된다.

    rev1=A와 rev2=B가 발행된 뒤 내용이 A로 돌아오면, 멱등 키에 기준
    판이 들어가므로 rev1을 만든 옛 승인 행과 부딪히지 않고 rev2를
    base로 한 새 계류가 생긴다. 승인하면 rev3=A로 현재 사실에
    돌아온다.
    """
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
    _run(uow)
    first_pending = _only_pending(uow)
    original_blocks = first_pending["blocks"]
    _publish(uow, revision_number=1)
    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    _run(uow)
    _publish(uow, revision_number=2)

    uow.knowledge_candidates.claims = [claim]
    result = _run(uow)

    assert result.proposals_conflicted == 0
    assert result.proposals_created == 1
    revert_pending = _only_pending(uow)
    assert revert_pending["blocks"] == original_blocks
    assert revert_pending["id"] != first_pending["id"]

    _publish(uow, revision_number=3)
    revision = uow.artifacts.revisions[-1]
    assert revision["revision_number"] == 3
    assert revision["blocks"] == serialize_blocks(original_blocks)


def test_conflicting_node_is_isolated_from_the_rest() -> None:
    """결정 행과 키가 부딪힌 노드만 접고 나머지 노드는 그대로 돈다.

    기준 판이 키에 들어간 뒤로 정상 흐름에서는 이 충돌이 나지 않는다.
    그래도 데이터 이상으로 부딪히면 실행 전체가 죽는 대신 그 노드만
    건너뛰어야 한다. 저장 계층을 이상 상태 대신 직접 흉내 낸다.
    """
    first = uuid.uuid4()
    second = uuid.uuid4()
    uow = FakeUnitOfWork(
        nodes=[_node(first, "첫 기능"), _node(second, "둘째 기능")],
        claims=[_claim(node_id=first, value=60), _claim(node_id=second)],
    )
    original = uow.artifacts.add_or_revive_proposal

    def _raising(**kwargs: object) -> uuid.UUID:
        first_artifact = uow.artifacts.definition_artifacts.get(
            (DEFINITION_ID, first)
        )
        if kwargs["artifact_id"] == first_artifact:
            raise ArtifactProposalConflict("이상 상태 재현")
        return original(**kwargs)

    uow.artifacts.add_or_revive_proposal = _raising  # type: ignore[method-assign]

    result = _run(uow)

    assert result.nodes_considered == 2
    assert result.proposals_conflicted == 1
    assert result.proposals_created == 1
    row = _only_pending(uow)
    artifact_id = uow.artifacts.definition_artifacts[(DEFINITION_ID, second)]
    assert row["artifact_id"] == artifact_id


def test_skipped_node_abandons_stale_pending() -> None:
    """지문이 그대로라 넘기는 노드도 내용이 다른 낡은 계류는 접는다."""
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
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


def test_skipped_node_keeps_matching_pending_and_abandons_other_pending() -> None:
    """현재 내용의 계류안은 남기고 함께 남은 낡은 계류안만 접는다."""
    node_id = uuid.uuid4()
    claim = _claim(node_id=node_id, value=60)
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[claim])
    _run(uow)
    matching = _only_pending(uow)

    uow.knowledge_candidates.claims = [replace(claim, value=120)]
    _run(uow)
    stale = _only_pending(uow)
    matching["status"] = "pending"

    uow.knowledge_candidates.claims = [claim]
    result = _run(uow)

    assert result.unchanged_skipped == 1
    assert result.proposals_abandoned == 1
    assert matching["status"] == "pending"
    assert stale["status"] == "abandoned"


def test_fake_refuses_to_revive_decided_rows() -> None:
    """fake가 결정된 행의 되살리기를 실 DB처럼 거절한다."""
    repository = FakeArtifactRepository()
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


def test_closed_claims_leave_the_card() -> None:
    """구간이 닫힌 주장은 카드에도 Read Set에도 실리지 않는다."""
    node_id = uuid.uuid4()
    alive = _claim(node_id=node_id, value=60)
    closed = _claim(
        node_id=node_id, value=120, valid_to=NOW + timedelta(days=1)
    )
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[alive, closed])

    _run(uow)

    row = _only_pending(uow)
    blocks = row["blocks"]
    bodies = " ".join(block.body for block in blocks)
    assert "60" in bodies
    assert "120" not in bodies
    claim_ids = {
        claim_id for block in blocks for claim_id in block.claim_ids
    }
    assert alive.id in claim_ids
    assert closed.id not in claim_ids


def test_future_valid_from_claim_stays_on_the_card() -> None:
    """발효 예정인 주장도 카드에 실린다.

    컴파일러는 "닫힌 주장 제외" 의미론을 쓴다. valid_from이 미래인
    accepted claim은 아직 닫히지 않았으므로 조용히 빠지면 안 된다.
    """
    node_id = uuid.uuid4()
    alive = _claim(node_id=node_id, value=60)
    upcoming = _claim(
        node_id=node_id,
        predicate="is_supported",
        value=True,
        value_type="boolean",
        valid_from=NOW + timedelta(days=3650),
    )
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[alive, upcoming])

    _run(uow)

    row = _only_pending(uow)
    blocks = row["blocks"]
    claim_ids = {
        claim_id for block in blocks for claim_id in block.claim_ids
    }
    assert alive.id in claim_ids
    assert upcoming.id in claim_ids


def test_future_valid_to_claim_stays_on_the_card() -> None:
    """닫힘이 예정된 주장도 발효 전까지는 카드에 남는다.

    supersede 결정은 패자의 valid_to를 승자의 valid_from으로 닫는데,
    그 시각이 미래면 지금은 아직 닫힌 주장이 아니다. 발효 전에 미리
    지우면 카드가 "아직 참인 사실"을 감추게 된다.
    """
    node_id = uuid.uuid4()
    closing_soon = _claim(
        node_id=node_id,
        value=60,
        valid_to=datetime.now(timezone.utc) + timedelta(days=30),
    )
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)], claims=[closing_soon]
    )

    _run(uow)

    row = _only_pending(uow)
    blocks = row["blocks"]
    claim_ids = {
        claim_id for block in blocks for claim_id in block.claim_ids
    }
    assert closing_soon.id in claim_ids
    assert "60" in " ".join(block.body for block in blocks)


def test_section_disappears_when_every_value_is_closed() -> None:
    """한 속성의 값이 전부 닫히면 그 절 자체가 사라진다."""
    node_id = uuid.uuid4()
    closed = _claim(
        node_id=node_id,
        predicate="rate_limit",
        value=60,
        valid_to=NOW + timedelta(days=1),
    )
    alive = _claim(node_id=node_id, predicate="is_supported", value=True,
                   value_type="boolean")
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[closed, alive])

    _run(uow)

    row = _only_pending(uow)
    headings = [block.heading for block in row["blocks"]]
    assert "rate_limit" not in headings
    assert "is_supported" in headings


def test_claim_section_sources_follow_member_order() -> None:
    """근거 인용이 claim_ids와 같은 순서로 원본 그대로 실린다."""
    node_id = uuid.uuid4()
    older = _claim(
        node_id=node_id, value=60, minutes=0, citation_verified=True
    )
    newer = _claim(
        node_id=node_id, value=120, minutes=30, citation_verified=False
    )
    # 입력 순서를 관찰 시각 역순으로 준다. 정렬이 sources에도 걸리는지
    # 보려면 입력 순서와 기대 순서가 달라야 한다.
    uow = FakeUnitOfWork(nodes=[_node(node_id)], claims=[newer, older])

    _run(uow)

    block = _only_pending(uow)["blocks"][0]
    assert block.claim_ids == (older.id, newer.id)
    assert [source.claim_id for source in block.sources] == [
        older.id,
        newer.id,
    ]
    assert [source.statement for source in block.sources] == [
        older.statement,
        newer.statement,
    ]
    assert [source.observed_at for source in block.sources] == [
        older.observed_at,
        newer.observed_at,
    ]
    assert [source.citation_verified for source in block.sources] == [
        True,
        False,
    ]


def test_open_question_sources_skip_missing_statement() -> None:
    """statement가 없는 값 후보는 근거 인용에서 빠진다.

    한쪽 값이 닫혀 대조가 서지 않는 안건을 쓴다. 대조로 실리면 인용을
    metadata가 아니라 claim에서 만들므로 이 규칙이 걸리지 않는다.
    """
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(
        node_id=node_id,
        value=120,
        minutes=30,
        valid_to=NOW + timedelta(days=1),
    )
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, newer.id))
    values = proposal.resolver_metadata["values"]
    assert isinstance(values, list)
    proposal = replace(
        proposal,
        resolver_metadata={
            **proposal.resolver_metadata,
            "values": [
                values[0],
                {
                    key: value
                    for key, value in values[1].items()
                    if key != "statement"
                },
            ],
        },
    )
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [proposal]},
    )

    _run(uow)

    question = _only_pending(uow)["blocks"][-1]
    # 값 후보는 둘이지만 인용은 statement를 가진 하나뿐이다.
    assert question.claim_ids == (older.id, newer.id)
    assert [source.claim_id for source in question.sources] == [older.id]
    assert question.sources[0].statement == "rate_limit는 60이다"
    assert question.sources[0].observed_at == NOW
    assert question.sources[0].citation_verified is None


def test_rejected_block_is_dropped_from_the_next_compile() -> None:
    """사람이 반려한 블록은 같은 내용이면 다시 실리지 않는다."""
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
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
    _run(uow)
    first = _only_pending(uow)
    assert [block.heading for block in first["blocks"]] == [
        "release_month",
        "rate_limit",
    ]
    _reject_block(uow, proposal_id=first["id"], block_index=0)

    result = _run(uow)

    assert result.blocks_suppressed == 1
    fresh = _only_pending(uow)
    assert [block.heading for block in fresh["blocks"]] == ["rate_limit"]
    assert fresh["content_hash"] == blocks_content_hash(fresh["blocks"])


def test_rejected_contested_block_reopens_its_question() -> None:
    """반려로 빠진 대조 블록의 안건은 열린 질문으로 되살아난다.

    대조로 나간 안건은 열린 질문에서 이미 빠져 있다. 대조까지 반려로
    사라지면 계류인 안건이 카드 어디에도 없어, 사람이 다시 만날 길이
    없어진다. 반려된 것은 대조라는 표현 방식이지 안건 자체가 아니다.
    """
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    contradiction = _contradiction(
        node_id=node_id, claim_ids=(older.id, newer.id)
    )
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [contradiction]},
    )
    _run(uow)
    first = _only_pending(uow)
    assert [block.block_kind for block in first["blocks"]] == [
        BLOCK_KIND_CONTESTED
    ]
    _reject_block(uow, proposal_id=first["id"], block_index=0)

    result = _run(uow)

    assert result.blocks_suppressed == 1
    fresh = _only_pending(uow)
    kinds = [block.block_kind for block in fresh["blocks"]]
    assert BLOCK_KIND_CONTESTED not in kinds
    assert kinds == [BLOCK_KIND_OPEN_QUESTION]
    assert fresh["blocks"][0].proposal_ids == (contradiction.id,)
    assert fresh["content_hash"] == blocks_content_hash(fresh["blocks"])
    validate_blocks(fresh["blocks"])
    # 되살린 카드도 같은 입력이면 같은 본문이라 다시 쌓이지 않는다.
    assert _run(uow).unchanged_skipped == 1


def test_reopened_question_can_be_rejected_too() -> None:
    """되살린 열린 질문도 반려하면 다시 올라오지 않는다.

    되살리기가 반려 장부를 건너뛰면 사람이 두 형태를 모두 물려도 같은
    안건이 영원히 되돌아온다.
    """
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    contradiction = _contradiction(
        node_id=node_id, claim_ids=(older.id, newer.id)
    )
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [contradiction]},
    )
    _run(uow)
    _reject_block(uow, proposal_id=_only_pending(uow)["id"], block_index=0)
    _run(uow)
    _reject_block(uow, proposal_id=_only_pending(uow)["id"], block_index=0)

    result = _run(uow)

    assert result.blocks_suppressed == 2
    assert uow.artifacts.pending_rows() == []


def test_changed_block_reappears_after_rejection() -> None:
    """반려된 블록도 내용이 바뀌면 다시 검토 큐에 오른다."""
    node_id = uuid.uuid4()
    month = _claim(
        node_id=node_id,
        predicate="release_month",
        value="2026-09",
        value_type="date",
    )
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[_claim(node_id=node_id, value=60), month],
    )
    _run(uow)
    _reject_block(uow, proposal_id=_only_pending(uow)["id"], block_index=0)
    _run(uow)

    uow.knowledge_candidates.claims = [
        _claim(node_id=node_id, value=60),
        replace(month, value="2026-10"),
    ]
    result = _run(uow)

    assert result.blocks_suppressed == 0
    fresh = _only_pending(uow)
    assert [block.heading for block in fresh["blocks"]] == [
        "release_month",
        "rate_limit",
    ]
    assert fresh["blocks"][0].body == "2026-10 (2026-07-30 관찰)"


def test_node_with_every_block_rejected_is_skipped() -> None:
    """블록이 모두 반려로 빠지면 빈 카드 대신 계류를 접는다.

    남은 계류는 방금 반려된 본문을 담고 있다. 그대로 두면 사람이 같은
    것을 검토 큐에서 또 만난다.
    """
    node_id = uuid.uuid4()
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[_claim(node_id=node_id, value=60)],
    )
    _run(uow)
    stale_id = _only_pending(uow)["id"]
    _reject_block(uow, proposal_id=stale_id, block_index=0)

    result = _run(uow)

    assert result.blocks_suppressed == 1
    assert result.proposals_created == 0
    assert result.proposals_revived == 0
    assert result.proposals_abandoned == 1
    assert uow.artifacts.pending_rows() == []
    assert uow.artifacts.by_id[stale_id]["status"] == "abandoned"


def test_compiled_blocks_pass_validation_with_sources() -> None:
    """근거 인용이 붙은 컴파일 산출 블록이 부분집합 규칙을 지킨다."""
    node_id = uuid.uuid4()
    older = _claim(node_id=node_id, value=60, minutes=0)
    newer = _claim(node_id=node_id, value=120, minutes=30)
    proposal = _contradiction(node_id=node_id, claim_ids=(older.id, newer.id))
    uow = FakeUnitOfWork(
        nodes=[_node(node_id)],
        claims=[older, newer],
        pending={node_id: [proposal]},
    )

    _run(uow)

    blocks = _only_pending(uow)["blocks"]
    validate_blocks(blocks)
    # 모순 안건은 대조 블록 하나로 접히므로 절과 질문이 따로 서지 않는다.
    assert len(blocks) == 1
    for block in blocks:
        assert block.sources
        assert {source.claim_id for source in block.sources} <= set(
            block.claim_ids
        )
