"""entity 해소 event 저널의 영속성 경계를 정의한다.

병합과 되돌림 확정 한 건을 덧붙이기만 하는 기록으로 남긴다. 판정 당시의
멤버 구성과 근거는 그 순간에만 존재해 사후에 다시 만들어 낼 수 없으므로,
확정과 같은 transaction에서 함께 적어 둔다.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from catchup.knowledge_maintenance.domain.source_version import JsonValue


@dataclass(frozen=True, slots=True)
class StoredResolutionEvent:
    """저널에 적힌 해소 event 한 건을 읽는 형태로 담는다.

    Attributes:
        id: event 행을 식별한다. 되돌림 행이 원본을 가리킬 때 쓰는 값이다.
        workspace_id: event가 속한 workspace다.
        event_type: 어떤 확정인지 나타낸다. 노드를 새로 세운 병합,
            이미 서 있는 노드로 붙인 병합, 되돌림 셋 중 하나다.
        decider: 사람이 정했는지 시스템이 정했는지 나타낸다.
        decider_id: 사람이 정했을 때 그 사람을 가리킨다. 시스템 확정에는
            없어 None이다.
        node_id: 확정이 다룬 canonical 노드를 가리킨다.
        member_hash: 판정에 묶인 멤버 구성을 한 값으로 줄인 것이다. 같은
            구성을 다시 다루는지 이 값으로 견준다.
        member_snapshot: 판정 당시의 멤버 구성을 그대로 담는다.
        basis: 판단 근거를 담는다.
        reverses_event_id: 되돌림 행이 되돌리는 원본 event를 가리킨다.
            병합 행에는 없어 None이다.
        created_at: 행이 적힌 시각이다.
    """

    id: uuid.UUID
    workspace_id: int
    event_type: str
    decider: str
    decider_id: str | None
    node_id: uuid.UUID
    member_hash: str
    member_snapshot: Mapping[str, JsonValue]
    basis: Mapping[str, JsonValue]
    reverses_event_id: uuid.UUID | None
    created_at: datetime


class ResolutionEventRepository(Protocol):
    """해소 event 저널의 영속성 기능을 정의한다."""

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
        member_snapshot: Mapping[str, JsonValue],
        basis: Mapping[str, JsonValue],
        reverses_event_id: uuid.UUID | None = None,
    ) -> None:
        """event 한 건을 저널에 덧붙인다.

        덧붙이기만 한다. 이미 적힌 행을 고치거나 지우는 자리는 두지
        않는다. 되돌림도 원본을 고치는 대신 원본을 가리키는 행을 새로
        적는다.

        `event_id`는 부르는 쪽이 만들어 넘긴다. 확정을 적기 전에 이미
        식별자가 정해져 있어야 같은 transaction 안에서 다른 기록이 그
        event를 가리킬 수 있기 때문이다.
        """
        ...

    def get(
        self, *, workspace_id: int, event_id: uuid.UUID
    ) -> StoredResolutionEvent | None:
        """event 한 건을 식별자로 읽는다. 없으면 None이다."""
        ...

    def find_reversal(
        self, *, workspace_id: int, event_id: uuid.UUID
    ) -> StoredResolutionEvent | None:
        """어떤 event를 되돌린 행을 찾는다. 없으면 None이다.

        되돌림을 두 번 하면 저널의 짝이 어긋난다. 되돌리기 전에 이
        조회로 이미 되돌려졌는지 보고, 있으면 두 번째 요청을 거부한다.
        """
        ...

    def has_human_unmerge(
        self, *, workspace_id: int, member_hash: str
    ) -> bool:
        """같은 멤버 구성을 사람이 되돌린 적이 있는지 본다.

        사람이 갈라 놓은 구성을 판정기가 다시 붙이면 사람의 결정이
        조용히 뒤집힌다. 자동 병합 전에 이 조회로 걸러 다시 붙이지
        않게 한다. 시스템이 되돌린 것은 포함하지 않는다 — 사람의
        결정만 자동 판정을 막는다.
        """
        ...
