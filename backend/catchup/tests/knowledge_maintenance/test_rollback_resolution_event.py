"""운영자 되돌림 서비스의 계약을 fake 저장소로 확인한다.

되돌림은 event 하나를 한 트랜잭션 안에서 되감는다. 두 병합 종류는
되감는 의미가 다르고, 같은 event를 두 번 되돌리는 것과 되돌림 행을
다시 되돌리는 것은 거부해야 한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from types import TracebackType
from typing import Any
from typing import Self

import pytest
from sqlalchemy.exc import IntegrityError

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.ports.resolution_events import StoredResolutionEvent
from catchup.knowledge_maintenance.services.rollback_resolution_event import (
    RollbackError,
)
from catchup.knowledge_maintenance.services.rollback_resolution_event import (
    rollback_resolution_event,
)

WORKSPACE_ID = 1
MEMBER_HASH = "hash-1"
PROPOSED_NAME = "결제 기능"
# 대표가 병합 전에 쓰던 이름이다. 병합이 지은 PROPOSED_NAME과 다른 값으로
# 둔다. 두 값이 같으면 분리가 대표에게 어느 이름을 주는지 가릴 수 없다.
REPRESENTATIVE_NAME = "결제 시스템"
MEMBER_NAMES = [REPRESENTATIVE_NAME, "결제", "페이먼트"]


@dataclass
class FakeState:
    """후보·노드·별칭·event를 한 곳에 둔 공유 상태다."""

    candidates: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    nodes: list[KnowledgeNode] = field(default_factory=list)
    aliases: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add_candidate(self, *, resolved_node_id: uuid.UUID) -> uuid.UUID:
        candidate_id = uuid.uuid4()
        self.candidates[candidate_id] = {
            "resolution_status": EntityResolutionStatus.MERGED.value,
            "resolved_node_id": resolved_node_id,
        }
        return candidate_id

    def add_node(self, *, display_name: str = "결제") -> KnowledgeNode:
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=WORKSPACE_ID,
            node_kind=NodeKind.ENTITY,
            entity_type="feature",
            canonical_key=None,
            display_name=display_name,
        )
        self.nodes.append(node)
        return node

    def node_by_id(self, node_id: uuid.UUID) -> KnowledgeNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise AssertionError(f"노드가 없다: {node_id}")

    def add_event(
        self,
        *,
        event_type: str,
        node_id: uuid.UUID,
        member_snapshot: Mapping[str, Any],
        reverses_event_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        event_id = uuid.uuid4()
        self.events.append(
            {
                "workspace_id": WORKSPACE_ID,
                "event_id": event_id,
                "event_type": event_type,
                "decider": "system",
                "decider_id": None,
                "node_id": node_id,
                "member_hash": MEMBER_HASH,
                "member_snapshot": dict(member_snapshot),
                "basis": {"detector": "catchup.name_block_partition"},
                "reverses_event_id": reverses_event_id,
            }
        )
        return event_id


@dataclass
class FakeCandidateRepo:
    state: FakeState

    def get_entity_resolution(
        self, *, candidate_id: uuid.UUID
    ) -> tuple[str, uuid.UUID | None] | None:
        row = self.state.candidates.get(candidate_id)
        if row is None:
            return None
        return (row["resolution_status"], row["resolved_node_id"])

    def count_entities_resolved_to(
        self, *, workspace_id: int, node_id: uuid.UUID
    ) -> int:
        return sum(
            1
            for row in self.state.candidates.values()
            if row["resolved_node_id"] == node_id
        )

    def mark_entity_resolved(
        self,
        *,
        candidate_id: uuid.UUID,
        status: EntityResolutionStatus,
        resolved_node_id: uuid.UUID,
    ) -> None:
        row = self.state.candidates[candidate_id]
        row["resolution_status"] = status.value
        row["resolved_node_id"] = resolved_node_id


@dataclass
class FakeNodeRepo:
    state: FakeState

    def create_entity_node(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        canonical_key: str | None,
        display_name: str,
        attributes: Mapping[str, object] | None = None,
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind=NodeKind.ENTITY,
            entity_type=entity_type,
            canonical_key=canonical_key,
            display_name=display_name,
            attributes=dict(attributes or {}),
        )
        self.state.nodes.append(node)
        return node

    def get_entity_by_id(
        self, *, workspace_id: int, node_id: uuid.UUID
    ) -> KnowledgeNode | None:
        for node in self.state.nodes:
            if node.workspace_id == workspace_id and node.id == node_id:
                return node
        return None

    def add_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        alias: str,
        normalized_alias: str,
        source: str,
    ) -> bool:
        for row in self.state.aliases:
            if (
                row["workspace_id"] == workspace_id
                and row["node_id"] == node_id
                and row["normalized_alias"] == normalized_alias
            ):
                return False
        self.state.aliases.append(
            {
                "workspace_id": workspace_id,
                "node_id": node_id,
                "alias": alias,
                "normalized_alias": normalized_alias,
                "source": source,
            }
        )
        return True

    def remove_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        normalized_alias: str,
    ) -> None:
        # 실 어댑터처럼 source가 'system'인 행만 지운다.
        self.state.aliases[:] = [
            row
            for row in self.state.aliases
            if not (
                row["workspace_id"] == workspace_id
                and row["node_id"] == node_id
                and row["normalized_alias"] == normalized_alias
                and row["source"] == "system"
            )
        ]

    def retire_entity_node(
        self, *, workspace_id: int, node_id: uuid.UUID
    ) -> None:
        for index, node in enumerate(self.state.nodes):
            if node.workspace_id == workspace_id and node.id == node_id:
                self.state.nodes[index] = KnowledgeNode(
                    id=node.id,
                    workspace_id=node.workspace_id,
                    node_kind=node.node_kind,
                    entity_type=node.entity_type,
                    canonical_key=node.canonical_key,
                    display_name=node.display_name,
                    lifecycle_state=NodeLifecycleState.RETIRED,
                )
                return
        raise AssertionError(f"노드가 없다: {node_id}")


@dataclass
class FakeResolutionEventRepo:
    state: FakeState

    def record(
        self,
        *,
        workspace_id: int,
        event_id: uuid.UUID,
        event_type: str,
        decider: str,
        decider_id: str | None,
        node_id: uuid.UUID,
        member_hash: str,
        member_snapshot: Mapping[str, Any],
        basis: Mapping[str, Any],
        reverses_event_id: uuid.UUID | None = None,
    ) -> None:
        self.state.events.append(
            {
                "workspace_id": workspace_id,
                "event_id": event_id,
                "event_type": event_type,
                "decider": decider,
                "decider_id": decider_id,
                "node_id": node_id,
                "member_hash": member_hash,
                "member_snapshot": dict(member_snapshot),
                "basis": dict(basis),
                "reverses_event_id": reverses_event_id,
            }
        )

    def get(
        self, *, workspace_id: int, event_id: uuid.UUID
    ) -> StoredResolutionEvent | None:
        for row in self.state.events:
            if row["workspace_id"] == workspace_id and row["event_id"] == event_id:
                return _to_stored(row)
        return None

    def find_reversal(
        self, *, workspace_id: int, event_id: uuid.UUID
    ) -> StoredResolutionEvent | None:
        for row in self.state.events:
            if (
                row["workspace_id"] == workspace_id
                and row["reverses_event_id"] == event_id
            ):
                return _to_stored(row)
        return None

    def has_human_unmerge(self, *, workspace_id: int, member_hash: str) -> bool:
        return any(
            row["workspace_id"] == workspace_id
            and row["member_hash"] == member_hash
            and row["event_type"] == "unmerge"
            and row["decider"] == "human"
            for row in self.state.events
        )


def _to_stored(row: Mapping[str, Any]) -> StoredResolutionEvent:
    return StoredResolutionEvent(
        id=row["event_id"],
        workspace_id=row["workspace_id"],
        event_type=row["event_type"],
        decider=row["decider"],
        decider_id=row["decider_id"],
        node_id=row["node_id"],
        member_hash=row["member_hash"],
        member_snapshot=dict(row["member_snapshot"]),
        basis=dict(row["basis"]),
        reverses_event_id=row["reverses_event_id"],
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
    )


@dataclass
class FakeUnitOfWork:
    state: FakeState
    committed: int = 0
    rolled_back: int = 0
    _snapshot: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.knowledge_candidates = FakeCandidateRepo(self.state)
        self.knowledge_nodes = FakeNodeRepo(self.state)
        self.resolution_events = FakeResolutionEventRepo(self.state)

    def __enter__(self) -> Self:
        import copy

        self._snapshot = {
            "candidates": copy.deepcopy(self.state.candidates),
            "nodes": list(self.state.nodes),
            "aliases": copy.deepcopy(self.state.aliases),
            "events": copy.deepcopy(self.state.events),
        }
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._snapshot is not None and self.committed == 0:
            self.state.candidates.clear()
            self.state.candidates.update(self._snapshot["candidates"])
            self.state.nodes[:] = self._snapshot["nodes"]
            self.state.aliases[:] = self._snapshot["aliases"]
            self.state.events[:] = self._snapshot["events"]
            self.rolled_back += 1

    def commit(self) -> None:
        self.committed += 1
        self._snapshot = None


def _applied(candidate_ids: list[uuid.UUID]) -> list[dict[str, str]]:
    """실제로 적용한 후보와 그 후보의 병합 전 이름을 저널 모양으로 만든다."""
    return [
        {"candidate_id": str(candidate_id), "name": name}
        for candidate_id, name in zip(candidate_ids, MEMBER_NAMES, strict=False)
    ]


def _seed_merge_into_node(state: FakeState) -> tuple[uuid.UUID, KnowledgeNode, list]:
    """기존 노드로 붙인 병합 event 하나를 심는다."""
    target = state.add_node()
    candidate_ids = [state.add_candidate(resolved_node_id=target.id) for _ in range(3)]
    state.aliases.append(
        {
            "workspace_id": WORKSPACE_ID,
            "node_id": target.id,
            "alias": "결제",
            "normalized_alias": normalize_name("결제"),
            "source": "extractor",
        }
    )
    state.aliases.append(
        {
            "workspace_id": WORKSPACE_ID,
            "node_id": target.id,
            "alias": PROPOSED_NAME,
            "normalized_alias": normalize_name(PROPOSED_NAME),
            "source": "system",
        }
    )
    event_id = state.add_event(
        event_type="merge_into_node",
        node_id=target.id,
        member_snapshot={
            "representative_candidate_id": str(candidate_ids[0]),
            "member_candidate_ids": [str(cid) for cid in candidate_ids[1:]],
            "member_names": list(MEMBER_NAMES),
            "proposed_name": PROPOSED_NAME,
            "proposed_type": "feature",
            "merge_into_node_id": str(target.id),
            "aliases_added": [PROPOSED_NAME],
            "applied_members": _applied(candidate_ids),
        },
    )
    return event_id, target, candidate_ids


def _seed_merge_create_node(state: FakeState) -> tuple[uuid.UUID, KnowledgeNode, list]:
    """새 노드를 세운 병합 event 하나를 심는다."""
    created = state.add_node(display_name=PROPOSED_NAME)
    candidate_ids = [state.add_candidate(resolved_node_id=created.id) for _ in range(3)]
    state.aliases.append(
        {
            "workspace_id": WORKSPACE_ID,
            "node_id": created.id,
            "alias": PROPOSED_NAME,
            "normalized_alias": normalize_name(PROPOSED_NAME),
            "source": "system",
        }
    )
    event_id = state.add_event(
        event_type="merge_create_node",
        node_id=created.id,
        member_snapshot={
            "representative_candidate_id": str(candidate_ids[0]),
            "member_candidate_ids": [str(cid) for cid in candidate_ids[1:]],
            "member_names": list(MEMBER_NAMES),
            "proposed_name": PROPOSED_NAME,
            "proposed_type": "feature",
            "merge_into_node_id": None,
            "aliases_added": [PROPOSED_NAME],
            "applied_members": _applied(candidate_ids),
        },
    )
    return event_id, created, candidate_ids


def test_merge_into_node_rollback_repoints_candidates_to_one_new_node() -> None:
    """기존 노드로 붙인 병합은 새 노드 하나로 되돌아간다."""
    state = FakeState()
    event_id, target, candidate_ids = _seed_merge_into_node(state)
    uow = FakeUnitOfWork(state)

    result = rollback_resolution_event(
        uow,
        workspace_id=WORKSPACE_ID,
        event_id=event_id,
        operator="ops:junsu",
    )

    assert uow.committed == 1
    assert len(result.new_node_ids) == 1
    new_node_id = result.new_node_ids[0]
    new_node = state.node_by_id(new_node_id)
    assert new_node.entity_type == "feature"
    assert new_node.display_name == PROPOSED_NAME
    assert set(result.repointed_candidate_ids) == set(candidate_ids)
    for candidate_id in candidate_ids:
        row = state.candidates[candidate_id]
        assert row["resolved_node_id"] == new_node_id
        assert row["resolution_status"] == EntityResolutionStatus.MERGED.value

    # 새 노드는 제 이름으로 불릴 수 있어야 한다.
    assert any(
        row["node_id"] == new_node_id
        and row["normalized_alias"] == normalize_name(PROPOSED_NAME)
        and row["source"] == "system"
        for row in state.aliases
    )
    # 대상 노드에서는 이번 병합이 남긴 별칭만 사라진다.
    assert result.removed_aliases == (PROPOSED_NAME,)
    remaining = [row for row in state.aliases if row["node_id"] == target.id]
    assert [row["alias"] for row in remaining] == ["결제"]

    unmerge = state.events[-1]
    assert unmerge["event_id"] == result.unmerge_event_id
    assert unmerge["event_type"] == "unmerge"
    assert unmerge["decider"] == "human"
    assert unmerge["decider_id"] == "ops:junsu"
    assert unmerge["reverses_event_id"] == event_id
    assert unmerge["member_hash"] == MEMBER_HASH
    assert unmerge["node_id"] == new_node_id
    assert unmerge["member_snapshot"]["reversed_event_id"] == str(event_id)
    assert state.node_by_id(target.id).lifecycle_state is NodeLifecycleState.ACTIVE


def test_second_rollback_of_same_event_is_rejected() -> None:
    """되돌림은 event당 한 번이다."""
    state = FakeState()
    event_id, _target, _candidate_ids = _seed_merge_into_node(state)
    uow = FakeUnitOfWork(state)
    rollback_resolution_event(
        uow,
        workspace_id=WORKSPACE_ID,
        event_id=event_id,
        operator="ops:junsu",
    )

    with pytest.raises(RollbackError):
        rollback_resolution_event(
            FakeUnitOfWork(state),
            workspace_id=WORKSPACE_ID,
            event_id=event_id,
            operator="ops:junsu",
        )


class _ConflictingEventRepo(FakeResolutionEventRepo):
    """되돌림 행을 적을 때 DB의 unique 위반을 흉내 낸다.

    두 운영자가 거의 동시에 같은 event를 되돌리면 미리 읽어 보는 검사는
    양쪽 다 통과하고, 나중에 적는 쪽이 DB 제약에서 부딪힌다.
    """

    def record(self, **kwargs: Any) -> None:
        if kwargs.get("reverses_event_id") is not None:
            raise IntegrityError(
                "INSERT INTO knowledge_resolution_events",
                {},
                Exception(
                    "duplicate key value violates unique constraint "
                    '"uq_knowledge_resolution_events_reversal"'
                ),
            )
        super().record(**kwargs)


def test_conflicting_reversal_is_reported_as_already_rolled_back() -> None:
    """DB가 막은 두 번째 되돌림은 이미 되돌려졌다는 거부로 읽힌다."""
    state = FakeState()
    event_id, _target, candidate_ids = _seed_merge_into_node(state)
    uow = FakeUnitOfWork(state)
    uow.resolution_events = _ConflictingEventRepo(state)

    with pytest.raises(RollbackError) as raised:
        rollback_resolution_event(
            uow,
            workspace_id=WORKSPACE_ID,
            event_id=event_id,
            operator="ops:junsu",
        )

    assert "이미 되돌려진 event다" in str(raised.value)
    assert uow.committed == 0
    # 트랜잭션이 되돌아가므로 후보도 제자리에 남는다.
    assert uow.rolled_back == 1
    for candidate_id in candidate_ids:
        assert state.candidates[candidate_id]["resolved_node_id"] is not None


def test_rollback_of_unmerge_event_is_rejected() -> None:
    """되돌림 행은 되돌림의 대상이 아니다."""
    state = FakeState()
    merge_event_id, _target, _candidate_ids = _seed_merge_into_node(state)
    unmerge_event_id = state.add_event(
        event_type="unmerge",
        node_id=uuid.uuid4(),
        member_snapshot={"reversed_event_id": str(merge_event_id)},
        reverses_event_id=merge_event_id,
    )

    with pytest.raises(RollbackError):
        rollback_resolution_event(
            FakeUnitOfWork(state),
            workspace_id=WORKSPACE_ID,
            event_id=unmerge_event_id,
            operator="ops:junsu",
        )


def test_merge_create_node_rollback_splits_candidates_and_retires_node() -> None:
    """스스로 세운 노드의 병합은 후보마다 제 노드로 갈라진다."""
    state = FakeState()
    event_id, created, candidate_ids = _seed_merge_create_node(state)
    uow = FakeUnitOfWork(state)

    result = rollback_resolution_event(
        uow,
        workspace_id=WORKSPACE_ID,
        event_id=event_id,
        operator="ops:junsu",
    )

    assert uow.committed == 1
    assert len(result.new_node_ids) == len(candidate_ids)
    assert len(set(result.new_node_ids)) == len(candidate_ids)
    assert set(result.repointed_candidate_ids) == set(candidate_ids)

    # 후보는 저마다 제 이름의 노드로 간다.
    resolved = [state.candidates[cid]["resolved_node_id"] for cid in candidate_ids]
    assert len(set(resolved)) == len(candidate_ids)
    names = [state.node_by_id(node_id).display_name for node_id in resolved]
    # 대표도 병합 전 제 이름으로 선다. 병합이 지은 이름을 그대로 주면
    # 갈라 놓은 노드가 병합의 작명을 계속 들고 다닌다.
    assert names == MEMBER_NAMES
    assert names[0] == REPRESENTATIVE_NAME
    assert names[0] != PROPOSED_NAME

    assert state.node_by_id(created.id).lifecycle_state is NodeLifecycleState.RETIRED
    # 후보가 떠난 노드는 통째로 물러나므로 별칭을 따로 지우지 않는다.
    assert result.removed_aliases == ()

    unmerge = state.events[-1]
    assert unmerge["event_type"] == "unmerge"
    assert unmerge["node_id"] == result.new_node_ids[0]
    assert unmerge["reverses_event_id"] == event_id
    assert unmerge["member_snapshot"]["node_retired"] is True


def test_rollback_moves_only_the_members_the_event_applied() -> None:
    """event가 실제로 붙이지 않은 후보는 되돌림도 건드리지 않는다.

    승인과 적용 사이에 멤버 하나가 다른 노드로 먼저 해소되면 적용은 그
    멤버를 건너뛴다. 저널의 판정 당시 구성에는 그 멤버가 남아 있으므로,
    되돌림이 구성을 그대로 믿으면 이 event와 무관한 선행 해소를 지운다.
    """
    state = FakeState()
    created = state.add_node(display_name=PROPOSED_NAME)
    foreign = state.add_node(display_name="다른 대상")
    applied_ids = [state.add_candidate(resolved_node_id=created.id) for _ in range(2)]
    skipped_id = state.add_candidate(resolved_node_id=foreign.id)
    event_id = state.add_event(
        event_type="merge_create_node",
        node_id=created.id,
        member_snapshot={
            "representative_candidate_id": str(applied_ids[0]),
            "member_candidate_ids": [str(applied_ids[1]), str(skipped_id)],
            "member_names": list(MEMBER_NAMES),
            "proposed_name": PROPOSED_NAME,
            "proposed_type": "feature",
            "merge_into_node_id": None,
            "aliases_added": [PROPOSED_NAME],
            "applied_members": _applied(applied_ids),
        },
    )

    result = rollback_resolution_event(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        event_id=event_id,
        operator="ops:junsu",
    )

    assert set(result.repointed_candidate_ids) == set(applied_ids)
    assert skipped_id not in result.repointed_candidate_ids
    # 먼저 해소돼 있던 후보는 제자리에 그대로 있다.
    assert state.candidates[skipped_id]["resolved_node_id"] == foreign.id
    assert len(result.new_node_ids) == len(applied_ids)


def test_rollback_skips_a_member_that_now_points_elsewhere() -> None:
    """event 이후 다른 노드로 옮겨진 후보는 되돌림이 덮지 않는다."""
    state = FakeState()
    event_id, created, candidate_ids = _seed_merge_create_node(state)
    moved = state.add_node(display_name="옮겨 간 대상")
    state.candidates[candidate_ids[2]]["resolved_node_id"] = moved.id

    result = rollback_resolution_event(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        event_id=event_id,
        operator="ops:junsu",
    )

    assert set(result.repointed_candidate_ids) == set(candidate_ids[:2])
    assert state.candidates[candidate_ids[2]]["resolved_node_id"] == moved.id
    assert len(result.new_node_ids) == 2
    assert state.node_by_id(created.id).lifecycle_state is NodeLifecycleState.RETIRED


def test_rollback_keeps_the_node_when_a_later_candidate_still_points_to_it() -> None:
    """event 이후 같은 노드로 해소된 후보가 있으면 노드를 물리지 않는다.

    노드를 조건 없이 물리면 그 후보와 그 후보로 읽히는 지식이 살아 있는
    graph에서 사라진다.
    """
    state = FakeState()
    event_id, created, candidate_ids = _seed_merge_create_node(state)
    later_id = state.add_candidate(resolved_node_id=created.id)

    result = rollback_resolution_event(
        FakeUnitOfWork(state),
        workspace_id=WORKSPACE_ID,
        event_id=event_id,
        operator="ops:junsu",
    )

    assert set(result.repointed_candidate_ids) == set(candidate_ids)
    assert state.node_by_id(created.id).lifecycle_state is NodeLifecycleState.ACTIVE
    assert state.candidates[later_id]["resolved_node_id"] == created.id

    unmerge = state.events[-1]
    assert unmerge["member_snapshot"]["node_retired"] is False


def test_rollback_without_applied_members_is_rejected() -> None:
    """무엇을 실제로 붙였는지 없는 event는 되돌리지 않는다."""
    state = FakeState()
    created = state.add_node(display_name=PROPOSED_NAME)
    candidate_id = state.add_candidate(resolved_node_id=created.id)
    event_id = state.add_event(
        event_type="merge_create_node",
        node_id=created.id,
        member_snapshot={
            "representative_candidate_id": str(candidate_id),
            "member_candidate_ids": [],
            "member_names": list(MEMBER_NAMES),
            "proposed_name": PROPOSED_NAME,
            "proposed_type": "feature",
            "merge_into_node_id": None,
            "aliases_added": [],
        },
    )

    with pytest.raises(RollbackError):
        rollback_resolution_event(
            FakeUnitOfWork(state),
            workspace_id=WORKSPACE_ID,
            event_id=event_id,
            operator="ops:junsu",
        )
