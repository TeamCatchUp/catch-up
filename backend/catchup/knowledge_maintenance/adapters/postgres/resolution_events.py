"""해소 event 저널 포트를 PostgreSQL 표로 구현한다.

해소의 session을 그대로 받아 쓴다. 저널 행은 확정과 같은 transaction에
있어야 하며, 나뉘면 붙이기는 됐는데 왜 붙였는지가 없는 상태나 그 반대가
남을 수 있기 때문이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import KnowledgeResolutionEvent as KnowledgeResolutionEventRow
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.ports.resolution_events import StoredResolutionEvent


class PostgresResolutionEventRepository:
    """해소 event를 덧붙이고 되짚는다.

    쓰기는 삽입뿐이다. 갱신도 삭제도 하지 않으므로 한 번 적힌 행은 그대로
    남고, 되돌림은 원본을 가리키는 행을 새로 적어 표현한다.
    """

    def __init__(self, session: Session) -> None:
        """해소와 같은 session을 받아 저장소를 만든다."""
        self._session = session

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

        곧바로 flush한다. 종류·결정자·되돌림 짝을 DB CHECK가 보고 있어,
        transaction 끝까지 미루면 어느 기록이 제약을 어겼는지 알기 어려운
        자리에서 실패한다.
        """
        self._session.add(
            KnowledgeResolutionEventRow(
                id=event_id,
                workspace_id=workspace_id,
                event_type=event_type,
                decider=decider,
                decider_id=decider_id,
                node_id=node_id,
                member_hash=member_hash,
                member_snapshot=dict(member_snapshot),
                basis=dict(basis),
                reverses_event_id=reverses_event_id,
            )
        )
        self._session.flush()

    def get(
        self, *, workspace_id: int, event_id: uuid.UUID
    ) -> StoredResolutionEvent | None:
        """event 한 건을 식별자로 읽는다. 없으면 None이다."""
        row = self._session.scalar(
            select(KnowledgeResolutionEventRow).where(
                KnowledgeResolutionEventRow.workspace_id == workspace_id,
                KnowledgeResolutionEventRow.id == event_id,
            )
        )
        return None if row is None else _to_stored(row)

    def find_reversal(
        self, *, workspace_id: int, event_id: uuid.UUID
    ) -> StoredResolutionEvent | None:
        """어떤 event를 되돌린 행을 찾는다. 없으면 None이다."""
        row = self._session.scalar(
            select(KnowledgeResolutionEventRow)
            .where(
                KnowledgeResolutionEventRow.workspace_id == workspace_id,
                KnowledgeResolutionEventRow.reverses_event_id == event_id,
            )
            .order_by(KnowledgeResolutionEventRow.created_at)
            .limit(1)
        )
        return None if row is None else _to_stored(row)

    def has_human_unmerge(
        self, *, workspace_id: int, member_hash: str
    ) -> bool:
        """같은 멤버 구성을 사람이 되돌린 적이 있는지 본다."""
        found = self._session.scalar(
            select(KnowledgeResolutionEventRow.id)
            .where(
                KnowledgeResolutionEventRow.workspace_id == workspace_id,
                KnowledgeResolutionEventRow.member_hash == member_hash,
                KnowledgeResolutionEventRow.event_type == "unmerge",
                KnowledgeResolutionEventRow.decider == "human",
            )
            .limit(1)
        )
        return found is not None


def _to_stored(row: KnowledgeResolutionEventRow) -> StoredResolutionEvent:
    """저장 행을 읽는 형태로 옮긴다."""
    return StoredResolutionEvent(
        id=row.id,
        workspace_id=row.workspace_id,
        event_type=row.event_type,
        decider=row.decider,
        decider_id=row.decider_id,
        node_id=row.node_id,
        member_hash=row.member_hash,
        member_snapshot=dict(row.member_snapshot or {}),
        basis=dict(row.basis or {}),
        reverses_event_id=row.reverses_event_id,
        created_at=row.created_at,
    )
