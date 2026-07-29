from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredEntityCandidate,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredMutationProposal,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    resolve_entity_candidates,
)

NOW = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
WORKSPACE = 1


def _candidate(
    *,
    name: str,
    entity_type: str = "channel_talk_user",
    method: ExtractionMethod = ExtractionMethod.DETERMINISTIC,
    external_key: str | None = None,
    minutes: int = 0,
) -> StoredEntityCandidate:
    attributes: dict[str, object] = {}
    if external_key is not None:
        attributes["external_key"] = external_key
    return StoredEntityCandidate(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        local_key="m1" if method is ExtractionMethod.DETERMINISTIC else "e1",
        proposed_type=entity_type,
        proposed_name=name,
        extraction_method=method,
        raw_payload={"attributes": attributes},
        source_type="channel_talk",
        created_at=NOW + timedelta(minutes=minutes),
    )


class FakeCandidateRepository:
    def __init__(self, candidates: list[StoredEntityCandidate]) -> None:
        self.candidates = list(candidates)
        self.resolved: dict[uuid.UUID, tuple[EntityResolutionStatus, uuid.UUID]] = {}

    def find_pending_entity_candidates(self, *, workspace_id: int):
        del workspace_id
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.id not in self.resolved
        )

    def mark_entity_resolved(self, *, candidate_id, status, resolved_node_id):
        self.resolved[candidate_id] = (status, resolved_node_id)


class FakeNodeRepository:
    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self.aliases: list[tuple[uuid.UUID, str]] = []

    def get_entity_by_canonical_key(self, *, workspace_id, canonical_key):
        del workspace_id
        return self.nodes.get(canonical_key)

    def create_entity_node(
        self, *, workspace_id, entity_type, canonical_key, display_name
    ):
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=NodeKind.ENTITY,
            entity_type=entity_type,
            canonical_key=canonical_key,
            display_name=display_name,
        )
        self.nodes[canonical_key] = node
        return node

    def add_alias(
        self, *, workspace_id, node_id, alias, normalized_alias, source
    ):
        del workspace_id, alias, source
        if (node_id, normalized_alias) not in self.aliases:
            self.aliases.append((node_id, normalized_alias))


class FakeProposalRepository:
    def __init__(self) -> None:
        self.proposals: dict[str, dict] = {}
        self.abandoned: list[uuid.UUID] = []

    def find_pending_by_idempotency_key(self, *, workspace_id, idempotency_key):
        del workspace_id
        found = self.proposals.get(idempotency_key)
        if found is None or found["status"] != "pending":
            return None
        return StoredMutationProposal(
            id=found["id"],
            idempotency_key=idempotency_key,
            status=found["status"],
            resolver_metadata=found["resolver_metadata"],
        )

    def abandon(self, *, proposal_id):
        self.abandoned.append(proposal_id)
        for record in self.proposals.values():
            if record["id"] == proposal_id:
                record["status"] = "abandoned"

    def add_duplicate_proposal(self, **kwargs):
        proposal_id = uuid.uuid4()
        self.proposals[kwargs["idempotency_key"]] = {
            "id": proposal_id,
            "status": "pending",
            "resolver_metadata": dict(kwargs["resolver_metadata"]),
            "kwargs": kwargs,
        }
        return proposal_id


class FakeUnitOfWork:
    def __init__(self, candidates: list[StoredEntityCandidate]) -> None:
        self.knowledge_candidates = FakeCandidateRepository(candidates)
        self.knowledge_nodes = FakeNodeRepository()
        self.mutation_proposals = FakeProposalRepository()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def commit(self) -> None:
        self.committed = True


def test_same_external_key_candidates_share_one_node() -> None:
    """같은 외부 ID의 후보들은 노드 하나로 모인다."""
    first = _candidate(name="캐치업 팀", external_key="manager-1")
    second = _candidate(name="캐치업 팀", external_key="manager-1", minutes=1)
    uow = FakeUnitOfWork([first, second])

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 1
    assert result.candidates_accepted == 1
    assert result.candidates_merged == 1
    statuses = uow.knowledge_candidates.resolved
    assert statuses[first.id][0] is EntityResolutionStatus.ACCEPTED
    assert statuses[second.id][0] is EntityResolutionStatus.MERGED
    assert statuses[first.id][1] == statuses[second.id][1]
    assert uow.committed


def test_different_external_keys_get_separate_nodes() -> None:
    """외부 ID가 다르면 이름이 같아도 다른 노드다."""
    uow = FakeUnitOfWork(
        [
            _candidate(name="캐치업 팀", external_key="manager-1"),
            _candidate(name="캐치업 팀", external_key="manager-2"),
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 2
    assert result.candidates_accepted == 2


def test_llm_candidate_merges_into_existing_canonical_key() -> None:
    """기존 canonical key와 정확히 일치하는 LLM 후보는 병합된다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="Slack",
                entity_type="platform",
                method=ExtractionMethod.LLM,
            )
        ]
    )
    existing = uow.knowledge_nodes.create_entity_node(
        workspace_id=WORKSPACE,
        entity_type="platform",
        canonical_key=f"platform:{normalize_name('Slack')}",
        display_name="Slack",
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    # 노드는 셋업이 미리 만든 것뿐이고, 서비스는 신규 발급하지 않는다.
    assert result.nodes_created == 0
    assert result.candidates_merged == 1
    resolved = uow.knowledge_candidates.resolved
    only = next(iter(resolved.values()))
    assert only == (EntityResolutionStatus.MERGED, existing.id)


def test_llm_candidate_with_new_name_stays_pending() -> None:
    """처음 보는 LLM 후보는 canonical로 창설하지 않는다."""
    uow = FakeUnitOfWork(
        [
            _candidate(
                name="결제 기능",
                entity_type="feature",
                method=ExtractionMethod.LLM,
            )
        ]
    )

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 0
    assert result.candidates_accepted == 0
    assert uow.knowledge_candidates.resolved == {}


def test_deterministic_without_external_key_stays_pending() -> None:
    """외부 ID가 없는 결정론 후보는 건드리지 않는다."""
    uow = FakeUnitOfWork([_candidate(name="캐치업 팀", external_key=None)])

    result = resolve_entity_candidates(
        workspace_id=WORKSPACE, judge=None, uow=uow
    )

    assert result.nodes_created == 0
    assert uow.knowledge_candidates.resolved == {}
