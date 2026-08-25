"""확정된 entity 병합 한 건을 운영자가 되돌린다.

되돌림은 저널에 적힌 event 하나를 지목해 그 병합이 후보들에게 남긴
자리를 되감는 일이다. 원본 행은 고치지 않는다. 대신 원본을 가리키는
unmerge 행을 새로 적어 "이 병합은 사람이 갈라 놓았다"를 남긴다. 그
표시가 있어야 자동 병합이 같은 구성을 다시 붙이지 않는다.

두 병합 종류는 되감는 의미가 다르다. 기존 노드로 붙인 병합
(merge_into_node)에서 event가 만든 것은 "저 노드에 붙인다"는 결정
하나뿐이므로, 그룹 안에서 후보들이 서로 같다는 판정은 그대로 두고 새
노드 하나로 통째로 옮긴다. 스스로 노드를 세운 병합
(merge_create_node)에서는 병합 자체가 event가 만든 것이므로 되돌림이
곧 분리다. 후보 전부를 새 노드 하나로 옮기면 같은 병합을 이름만 바꿔
다시 만드는 셈이라, 후보마다 제 이름의 노드를 따로 세운다.

되돌림은 event 이후 그 노드에 변화가 있으면 거부한다. 멤버가 다른 노드로
떠났거나 후보가 더 붙었으면 이 event만 골라 되돌릴 수 없다. 일부만
되돌리고 저널에 "되돌렸다"를 적으면 기록과 실제가 어긋난다.

되돌림은 노드와 후보 층까지만 손댄다. retire된 노드로 편찬된 위키 문서는
그대로 남고 재편찬 대상에서만 빠진다. 문서 정리는 별도 처리다.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from typing import Self

from sqlalchemy.exc import IntegrityError

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.knowledge_maintenance.ports.resolution_events import (
    ResolutionEventRepository,
)
from catchup.knowledge_maintenance.ports.resolution_events import StoredResolutionEvent
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

MERGE_INTO_NODE = "merge_into_node"
MERGE_CREATE_NODE = "merge_create_node"
UNMERGE = "unmerge"

# 되돌림이 세우는 노드의 별칭 출처다. 사람의 결정이 남긴 이름이라
# 병합이 쓰는 표시와 같은 값을 쓴다.
ALIAS_SOURCE = "system"

# 원본당 되돌림 행 하나를 지키는 부분 unique 인덱스의 이름이다. 저널 쓰기가
# 실패했을 때 그것이 중복 되돌림인지 다른 이유인지를 이 이름으로 가른다.
REVERSAL_UNIQUE_CONSTRAINT = "uq_knowledge_resolution_events_reversal"


class RollbackError(Exception):
    """되돌릴 수 없는 요청을 거부할 때 던진다."""


class RollbackUnitOfWork(Protocol):
    """되돌림이 쓰는 transaction 경계를 정의한다."""

    resolution_events: ResolutionEventRepository
    knowledge_candidates: KnowledgeCandidateRepository
    knowledge_nodes: KnowledgeNodeRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """되돌림 한 번의 결과를 표현한다.

    Attributes:
        unmerge_event_id: 이번에 적은 되돌림 행을 가리킨다.
        new_node_ids: 후보를 받아 준 새 노드들을 가리킨다. 첫 번째가
            대표 후보의 노드다.
        repointed_candidate_ids: 자리를 옮긴 후보들을 가리킨다.
        removed_aliases: 병합 대상 노드에서 지운 이름들을 담는다.
    """

    unmerge_event_id: uuid.UUID
    new_node_ids: tuple[uuid.UUID, ...]
    repointed_candidate_ids: tuple[uuid.UUID, ...]
    removed_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Member:
    """되돌릴 후보 하나와 그 후보가 병합 전에 쓰던 이름을 담는다."""

    candidate_id: uuid.UUID
    name: str


def rollback_resolution_event(
    uow: RollbackUnitOfWork,
    *,
    workspace_id: int,
    event_id: uuid.UUID,
    operator: str,
) -> RollbackResult:
    """병합 event 한 건을 되돌리고 되돌림 행을 남긴다.

    전부 한 트랜잭션이다. 후보 재배치와 되돌림 기록이 갈라지면 갈라 놓은
    자취는 남는데 그 사실을 아는 행이 없어, 자동 병합이 같은 구성을 다시
    붙인다.

    claim과 relation은 다시 키를 매기지 않는다. 읽기 경로가 노드를 직접
    가리키는 행과 그 노드로 해소된 후보를 가리키는 행을 함께 읽으므로,
    후보의 resolved_node_id를 옮기면 그 후보에 딸린 주장과 관계도 따라
    옮겨진다. 여기서 claim 행까지 손대면 같은 사실을 두 곳에 적는 셈이라
    한쪽이 어긋날 자리를 만든다.

    되감을 대상은 저널의 applied_members, 곧 그 병합이 실제로 옮긴 후보다.
    거기에 더해 event 이후 그 노드에 변화가 있으면 거부한다. 적용 직후에
    적어 둔 후보 집합과 지금 집합이 다르면 다른 결정이 끼어든 것이고, 그
    상태에서 이 event만 되돌리면 뒤의 결정을 지우거나 절반만 되돌린 상태를
    남긴다.

    Raises:
        RollbackError: event가 없거나, 되돌림 행이거나, 이미 되돌려졌거나,
            멤버 구성을 읽을 수 없거나, event 이후 노드에 변화가 있을 때
            던진다.
    """
    with uow:
        event = uow.resolution_events.get(
            workspace_id=workspace_id,
            event_id=event_id,
        )
        if event is None:
            raise RollbackError(f"되돌릴 event가 없다: {event_id}")
        if event.event_type == UNMERGE:
            raise RollbackError(
                f"되돌림 행은 되돌릴 수 없다: {event_id}"
            )
        existing = uow.resolution_events.find_reversal(
            workspace_id=workspace_id,
            event_id=event_id,
        )
        if existing is not None:
            raise RollbackError(
                f"이미 되돌려진 event다: {event_id} (되돌림 {existing.id})"
            )

        members = _members(event)
        proposed_type = _text(event.member_snapshot.get("proposed_type"))
        if not proposed_type:
            raise RollbackError(
                f"event에 entity 종류가 없다: {event_id}"
            )

        _require_unchanged_since_event(
            uow,
            workspace_id=workspace_id,
            event=event,
        )

        node_retired = False
        if event.event_type == MERGE_INTO_NODE:
            node_ids = _repoint_to_single_node(
                uow,
                workspace_id=workspace_id,
                members=members,
                proposed_type=proposed_type,
                # 이 경로는 후보들이 서로 같다는 판정을 그대로 두고 새 노드
                # 하나로 옮기므로, 그 노드의 이름은 병합이 지은
                # proposed_name이다. 대표의 병합 전 이름으로 되돌리는 것은
                # 분리 경로의 일이다.
                proposed_name=_text(event.member_snapshot.get("proposed_name")),
            )
            removed = _remove_added_aliases(
                uow,
                workspace_id=workspace_id,
                node_id=event.node_id,
                aliases=_texts(event.member_snapshot.get("aliases_added")),
            )
        else:
            node_ids = _split_into_own_nodes(
                uow,
                workspace_id=workspace_id,
                members=members,
                proposed_type=proposed_type,
            )
            # 멤버 전부가 노드를 떠났으므로 노드를 물린다. 집합 비교가
            # 이미 다른 후보가 붙어 있지 않음을 확인했고, 노드 행이 잠긴
            # 채라 그 사이에 후보가 새로 붙을 수도 없다. 저장소도 남은
            # 후보를 다시 확인하므로, 거짓이 돌아오면 잠금 규칙이 깨진
            # 것이라 되돌림 전체를 물린다.
            node_retired = uow.knowledge_nodes.retire_entity_node(
                workspace_id=workspace_id,
                node_id=event.node_id,
            )
            if not node_retired:
                raise RollbackError(
                    "후보를 옮긴 뒤에도 노드에 후보가 남아 있다. 잠금 규칙이 깨졌다"
                )
            removed = ()

        candidate_ids = tuple(member.candidate_id for member in members)
        unmerge_event_id = uuid.uuid4()
        try:
            uow.resolution_events.record(
                workspace_id=workspace_id,
                event_id=unmerge_event_id,
                event_type=UNMERGE,
                decider="human",
                decider_id=operator,
                node_id=node_ids[0],
                # 원본의 member_hash를 그대로 쓴다. 자동 병합은 "이 구성을
                # 사람이 갈라 놓았나"를 이 값으로 견주므로, 값이 달라지면
                # 되돌린 구성이 다시 붙는다.
                member_hash=event.member_hash,
                member_snapshot={
                    "reversed_event_id": str(event_id),
                    "new_node_ids": [str(node_id) for node_id in node_ids],
                    "repointed_candidate_ids": [
                        str(candidate_id) for candidate_id in candidate_ids
                    ],
                    "removed_aliases": list(removed),
                    # 노드를 물렸는지 저널에 남긴다. 병합 종류에 따라
                    # 정해지는 값이지만, 나중에 그래프만 봐서는 어느 쪽이었는지
                    # 구분되지 않는다.
                    "node_retired": node_retired,
                },
                basis={"operator": operator},
                reverses_event_id=event_id,
            )
        except IntegrityError as error:
            if not _is_duplicate_reversal(error):
                # 다른 제약을 어긴 것은 되돌림이 두 번 일어난 일이 아니다.
                # 여기서 함께 삼키면 저널이 왜 안 적혔는지가 사라진다.
                raise
            # 원본당 되돌림 행 하나라는 제약에 부딪혔다. 앞의 find_reversal
            # 검사는 잠금 없는 읽기라 거의 동시에 되돌리면 양쪽 다 통과하고,
            # 나중에 적는 쪽이 여기서 걸린다.
            raise RollbackError(
                f"이미 되돌려진 event다: {event_id}"
            ) from error
        uow.commit()

    logger.info(
        "resolution_event_rolled_back",
        workspace_id=workspace_id,
        event_id=str(event_id),
        event_type=event.event_type,
        unmerge_event_id=str(unmerge_event_id),
        operator=operator,
        new_node_count=len(node_ids),
        repointed_candidate_count=len(candidate_ids),
        removed_alias_count=len(removed),
        node_retired=node_retired,
    )
    return RollbackResult(
        unmerge_event_id=unmerge_event_id,
        new_node_ids=node_ids,
        repointed_candidate_ids=candidate_ids,
        removed_aliases=removed,
    )


def _repoint_to_single_node(
    uow: RollbackUnitOfWork,
    *,
    workspace_id: int,
    members: Sequence[_Member],
    proposed_type: str,
    proposed_name: str,
) -> tuple[uuid.UUID, ...]:
    """후보 전부를 새로 세운 노드 하나로 옮긴다.

    기존 노드에 붙인 결정만 되돌린다. 후보들이 서로 같은 대상이라는
    판정은 이 event가 만든 것이 아니므로 함께 풀지 않는다.
    """
    node_id = _create_named_node(
        uow,
        workspace_id=workspace_id,
        entity_type=proposed_type,
        name=proposed_name,
    )
    for member in members:
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=member.candidate_id,
            status=EntityResolutionStatus.MERGED,
            resolved_node_id=node_id,
        )
    return (node_id,)


def _split_into_own_nodes(
    uow: RollbackUnitOfWork,
    *,
    workspace_id: int,
    members: Sequence[_Member],
    proposed_type: str,
) -> tuple[uuid.UUID, ...]:
    """후보마다 제 이름의 노드를 세워 갈라 놓는다."""
    node_ids = []
    for member in members:
        node_id = _create_named_node(
            uow,
            workspace_id=workspace_id,
            entity_type=proposed_type,
            name=member.name,
        )
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=member.candidate_id,
            status=EntityResolutionStatus.MERGED,
            resolved_node_id=node_id,
        )
        node_ids.append(node_id)
    return tuple(node_ids)


def _create_named_node(
    uow: RollbackUnitOfWork,
    *,
    workspace_id: int,
    entity_type: str,
    name: str,
) -> uuid.UUID:
    """이름 하나로 canonical 노드를 세우고 그 이름을 별칭으로 남긴다.

    canonical_key는 비운다. 되돌림이 세우는 노드에는 외부 ID가 없어
    만들 키가 없다. 그래서 별칭은 선택이 아니다. 별칭이 없으면 읽기
    경로가 방금 세운 노드를 어떤 이름으로도 찾지 못한다.
    """
    node = uow.knowledge_nodes.create_entity_node(
        workspace_id=workspace_id,
        entity_type=entity_type,
        canonical_key=None,
        display_name=name,
    )
    uow.knowledge_nodes.add_alias(
        workspace_id=workspace_id,
        node_id=node.id,
        alias=name,
        normalized_alias=normalize_name(name),
        source=ALIAS_SOURCE,
    )
    return node.id


def _remove_added_aliases(
    uow: RollbackUnitOfWork,
    *,
    workspace_id: int,
    node_id: uuid.UUID,
    aliases: Sequence[str],
) -> tuple[str, ...]:
    """병합이 대상 노드에 남긴 이름을 지운다.

    저널의 aliases_added는 계획이 아니라 그 병합이 실제로 적은 이름
    목록이다. 대표가 이미 서 있던 노드를 재사용해 이름을 더하지 않은
    경우에는 비어 있고, 그때는 지울 것도 없다.

    그 이름을 쓰는 다른 후보가 남아 있는지는 여기서 보지 않는다. 그런
    후보가 있었다면 event 이후 노드에 후보가 더 붙은 것이고, 집합 비교가
    이미 되돌림을 거부했다.
    """
    removed = []
    for alias in aliases:
        if not alias.strip():
            continue
        uow.knowledge_nodes.remove_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            normalized_alias=normalize_name(alias),
        )
        removed.append(alias)
    return tuple(removed)


def _members(event: StoredResolutionEvent) -> tuple[_Member, ...]:
    """event snapshot에서 되돌릴 후보와 그 이름을 꺼낸다.

    읽는 것은 applied_members다. 그 병합이 실제로 해소 상태를 바꾼 후보만
    들어 있다. 판정 당시 구성인 member_candidate_ids를 읽으면, 승인과 적용
    사이에 다른 노드로 먼저 해소돼 적용이 건너뛴 후보까지 끌어와 이 병합과
    무관한 선행 해소를 지운다.

    이름도 저널에 적힌 것을 쓴다. 후보 행은 그동안 다른 상태로 바뀌었을 수
    있어 다시 읽지 않는다. 첫 번째가 대표이고, 그 이름은 대표가 병합 전에
    쓰던 이름이다. proposed_name은 병합이 지은 새 이름이라, 분리 경로에서
    그것을 쓰면 갈라 놓은 대표가 병합의 작명을 그대로 들고 다시 선다.
    이름이 비어 있을 때만 proposed_name으로 물러난다.

    Raises:
        RollbackError: 실적용 목록이나 병합 이름이 snapshot에 없을 때
            던진다.
    """
    snapshot: Mapping[str, JsonValue] = event.member_snapshot
    proposed_name = _text(snapshot.get("proposed_name"))
    if not proposed_name:
        raise RollbackError(f"event에 병합 이름이 없다: {event.id}")

    applied = snapshot.get("applied_members")
    if not isinstance(applied, list) or not applied:
        raise RollbackError(
            f"event에 실제로 적용한 후보 목록이 없다: {event.id}"
        )

    members = []
    for entry in applied:
        if not isinstance(entry, Mapping):
            raise RollbackError(
                f"event의 실적용 후보를 읽을 수 없다: {entry} (event {event.id})"
            )
        name = _text(entry.get("name"))
        members.append(
            _Member(
                candidate_id=_candidate_id(
                    entry.get("candidate_id"), event_id=event.id
                ),
                name=name or proposed_name,
            )
        )
    return tuple(members)


def _is_duplicate_reversal(error: IntegrityError) -> bool:
    """되돌림 행이 원본당 하나라는 제약을 어긴 것인지 본다.

    psycopg는 위반한 제약 이름을 원본 예외의 진단 정보에 담아 준다. 그
    값을 먼저 보고, 드라이버가 달라 진단 정보가 없으면 예외 문구에서
    제약 이름을 찾는다. 문구만 보고 넓게 잡으면 다른 제약을 어긴 실패까지
    "이미 되돌려졌다"로 읽혀 저널이 왜 안 적혔는지가 사라진다.
    """
    original = getattr(error, "orig", None)
    diagnostic = getattr(original, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == REVERSAL_UNIQUE_CONSTRAINT
    return REVERSAL_UNIQUE_CONSTRAINT in str(error)


def _require_unchanged_since_event(
    uow: RollbackUnitOfWork,
    *,
    workspace_id: int,
    event: StoredResolutionEvent,
) -> None:
    """event 이후 그 노드에 아무 일도 없었는지 본다. 있었으면 거부한다.

    노드 행을 먼저 잠근다. 후보를 붙이는 경로와 노드를 물리는 경로가 같은
    행을 잠그므로, 잠금을 얻은 뒤 읽은 집합은 이 트랜잭션이 끝날 때까지
    바뀌지 않는다.

    견주는 값은 event가 적용 직후에 적은 후보 집합이다. 지금 집합이 그것과
    다르면 멤버가 떠났거나(다른 결정이 옮겼다) 후보가 더 붙은 것이다(뒤의
    병합). 어느 쪽이든 이 event만 골라 되돌릴 수 없다. 일부만 되돌리면
    "되돌렸다"는 저널과 실제가 어긋난다.

    Raises:
        RollbackError: snapshot에 집합이 없거나, 노드가 없거나 active가
            아니거나, 집합이 다를 때 던진다.
    """
    recorded_raw = event.member_snapshot.get("node_candidate_ids_after")
    if not isinstance(recorded_raw, list):
        raise RollbackError(
            f"event에 실행 직후 후보 집합(node_candidate_ids_after)이 없다: {event.id}"
        )
    recorded = {_candidate_id(item, event_id=event.id) for item in recorded_raw}

    node = uow.knowledge_nodes.lock_entity_node(
        workspace_id=workspace_id, node_id=event.node_id
    )
    if node is None:
        raise RollbackError(f"event의 노드가 없다: {event.node_id}")
    if node.lifecycle_state is not NodeLifecycleState.ACTIVE:
        raise RollbackError(
            f"event의 노드가 살아 있지 않다: {event.node_id} ({node.lifecycle_state.value})"
        )

    current = set(
        uow.knowledge_candidates.list_entity_candidate_ids_resolved_to(
            workspace_id=workspace_id, node_id=event.node_id
        )
    )
    left = sorted(str(item) for item in recorded - current)
    attached = sorted(str(item) for item in current - recorded)
    if left:
        raise RollbackError(
            f"event 이후 노드를 떠난 후보: {left} (event {event.id})"
        )
    if attached:
        raise RollbackError(
            f"event 이후 노드에 붙은 후보: {attached}. "
            f"뒤에 일어난 event를 먼저 되돌려라 (event {event.id})"
        )


def _candidate_id(raw: object, *, event_id: uuid.UUID) -> uuid.UUID:
    """snapshot에 문자열로 적힌 후보 id를 읽는다.

    Raises:
        RollbackError: 값을 id로 읽을 수 없을 때 던진다.
    """
    try:
        return uuid.UUID(str(raw))
    except ValueError as error:
        raise RollbackError(
            f"event의 후보 id를 읽을 수 없다: {raw} (event {event_id})"
        ) from error


def _text(value: object) -> str:
    """snapshot 값을 문자열로 읽는다. 없으면 빈 문자열이다."""
    return "" if value is None else str(value)


def _texts(value: object) -> list[str]:
    """snapshot 값을 문자열 목록으로 읽는다. 목록이 아니면 비운다."""
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value]
