"""검색 projection의 쓰기 경계를 정의한다.

검색 인덱스는 원장에서 rebuild 가능한 projection이지 canonical이
아니다. 그래서 이 포트는 "다시 만든다"만 노출한다 — 어떤 vector DB를
쓰는지는 adapter만 안다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.search_projection import ProjectionDocument


@dataclass(frozen=True, slots=True)
class ProjectionRebuildResult:
    """rebuild 한 번이 움직인 행 수를 담는다.

    Attributes:
        deleted: 지워진 기존 projection 문서 수를 나타낸다.
        inserted: 새로 넣은 문서 수를 나타낸다.
    """

    deleted: int
    inserted: int


class ArtifactSearchProjectionPort(Protocol):
    """검색 projection의 쓰기 경계를 정의한다.

    이번 슬라이스의 전파 경로는 rebuild 하나뿐이며, 증분 upsert는
    Poller 상시화 때 추가한다. `ProjectionDocument.document_id`에
    revision_id가 없으므로 부분 upsert는 낡은 판의 블록을 남긴다 —
    전량 교체가 정합성의 근거다.
    """

    def rebuild(
        self,
        *,
        workspace_id: int,
        documents: Sequence[ProjectionDocument],
    ) -> ProjectionRebuildResult:
        """workspace의 llm_wiki 문서를 전량 교체한다."""
        ...
