"""검토를 기다리는 문서 변경안을 하나의 큐로 모아 읽는다.

정렬은 created_at 오름차순 하나다. 오래 기다린 안건이 먼저 보인다. 충돌
여부는 정렬에 쓰지 않고 contains_conflict 필드와 필터로만 드러낸다.

거르기와 자르기는 저장소가 아니라 이 서비스에서 한다. 계류 안건을 전부
읽어 Python에서 거른 뒤 자른다. MVP 규모(workspace당 수십~수백 건)에서
받아들일 비용이며, 이 수가 커지면 필터와 정렬을 SQL로 내리는 것이 다음
수순이다.

충돌 판정은 본문의 다툼(contested) 블록 유무로 한다. 컴파일러가 값이 갈린
속성을 contested 블록으로 옮겨 적으므로, 그 블록이 있다는 것이 곧 "이
안건에 사람이 골라야 할 것이 있다"는 뜻이다.

대상 노드로 판정하던 옛 경로는 걷어냈다. 목록의 표시와 상세의 충돌 목록이
서로 다른 사실에서 나와, 서로 다른 이유로 어긋날 수 있었기 때문이다.
유도가 하나면 그 어긋남이 성립하지 않는다.

표시가 켜졌는데 목록이 비는 것 자체는 지금도 가능하다. 다툼 블록이 가리킨
안건이 먼저 판정되면 계류 목록에서 빠지기 때문이다. 그때 표시가 말하는
것은 "본문에 다툼 블록이 있다"는 사실 그대로이고, 빈 목록은 그 안건이
이미 결정됐다는 뜻이다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.domain.artifact import BLOCK_KIND_CONTESTED
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.ports.artifacts import ArtifactRepository
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

# 목록 한 줄에 들어갈 요약의 길이 상한이다. 큐는 훑어보는 화면이라
# 본문을 통째로 실으면 오히려 고르기 어려워진다.
SUMMARY_MAX_LENGTH = 160


class ReviewQueueUnitOfWork(Protocol):
    """검토 큐 조회가 쓰는 읽기 전용 transaction 경계를 정의한다.

    commit을 요구하지 않는다. 이 경로는 아무것도 쓰지 않기 때문이다.
    저장소가 artifact 하나뿐인 이유는 충돌 표시가 본문 블록에서 나오기
    때문이다 — mutation 쪽을 함께 읽던 자리는 사라졌다.
    """

    artifacts: ArtifactRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    """검토 큐 한 줄을 표현한다.

    Attributes:
        proposal_id: 이 줄이 가리키는 변경안을 식별한다.
        artifact_id: 변경안이 붙은 문서를 가리킨다.
        title: 문서 제목을 보존한다.
        status: 변경안의 검토 상태를 나타낸다.
        summary: 본문에서 조립한 한 줄 요약을 담는다.
        origin: 변경안이 어디서 왔는지 나타낸다.
        contains_conflict: 이 문서의 대상에 계류 중인 모순이 걸려 있는지
            나타낸다. 정렬에는 쓰지 않고 표시와 거르기에만 쓴다.
        created_at: 변경안이 올라온 시각을 나타낸다.
    """

    proposal_id: uuid.UUID
    artifact_id: uuid.UUID
    title: str | None
    status: str
    summary: str
    origin: str
    contains_conflict: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewQueuePage:
    """큐의 한 페이지를 표현한다.

    Attributes:
        items: 이 페이지에 실린 줄들이다. 이미 정렬된 순서다.
        total: 거르기를 적용한 뒤의 전체 수다. 페이지 크기와 무관하다.
    """

    items: tuple[ReviewQueueItem, ...]
    total: int


def list_review_queue(
    uow: ReviewQueueUnitOfWork,
    *,
    workspace_id: int,
    contains_conflict: bool | None = None,
    artifact_ids: frozenset[uuid.UUID] | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ReviewQueuePage:
    """계류 중인 변경안을 오래된 순으로 한 페이지 읽는다.

    거르기 인자는 모두 생략 가능하고, 준 것만 차례로 좁힌다.
    `artifact_ids`에 빈 집합을 주면 빈 페이지가 된다. 아무 문서도 고르지
    않은 조건과 조건 없음을 같게 다루면 화면이 남의 문서를 보게 된다.

    total도 거른 뒤의 수다. 거른 목록의 마지막 쪽을 세는 근거이므로
    거르기 전 수를 주면 호출자가 빈 쪽을 요청하게 된다.

    Raises:
        ValueError: limit이나 offset이 음수일 때 던진다.
    """
    if limit < 0:
        raise ValueError("limit은 음수일 수 없다")
    if offset < 0:
        raise ValueError("offset은 음수일 수 없다")

    with uow:
        proposals = uow.artifacts.list_pending_proposals()

    items = [_to_item(proposal) for proposal in proposals]
    if contains_conflict is not None:
        items = [
            item
            for item in items
            if item.contains_conflict is contains_conflict
        ]
    if artifact_ids is not None:
        items = [item for item in items if item.artifact_id in artifact_ids]
    if created_after is not None:
        items = [item for item in items if item.created_at >= created_after]
    if created_before is not None:
        items = [item for item in items if item.created_at <= created_before]
    # 오래된 순 하나다. 시각이 같은 줄은 proposal_id로 갈라 순서를 고정한다.
    items.sort(key=lambda item: (item.created_at, str(item.proposal_id)))

    total = len(items)
    page = tuple(items[offset : offset + limit])
    logger.info(
        "review_queue_listed",
        workspace_id=workspace_id,
        total=total,
        returned=len(page),
        conflict_count=sum(1 for item in items if item.contains_conflict),
    )
    return ReviewQueuePage(items=page, total=total)


def _to_item(proposal: StoredArtifactProposal) -> ReviewQueueItem:
    """변경안 하나를 큐 한 줄로 옮긴다."""
    return ReviewQueueItem(
        proposal_id=proposal.id,
        artifact_id=proposal.artifact_id,
        title=proposal.title,
        status=proposal.status,
        summary=_summary(proposal.blocks),
        origin=proposal.origin,
        contains_conflict=any(
            block.block_kind == BLOCK_KIND_CONTESTED
            for block in proposal.blocks
        ),
        created_at=proposal.created_at,
    )


def _summary(blocks: tuple[ArtifactBlock, ...]) -> str:
    """첫 블록의 제목과 본문 첫 줄로 한 줄 요약을 조립한다.

    제목만으로는 같은 속성을 다루는 안건들이 구별되지 않고, 본문 전체는
    목록에 실을 수 없다. 첫 줄까지가 "무엇이 달라졌나"를 가리는 최소
    단위다. 블록이 없으면 빈 문자열이다.
    """
    if not blocks:
        return ""
    block = blocks[0]
    lines = [line.strip() for line in block.body.splitlines() if line.strip()]
    parts = [part for part in (block.heading.strip(), *lines[:1]) if part]
    summary = ": ".join(parts)
    if len(summary) > SUMMARY_MAX_LENGTH:
        return summary[: SUMMARY_MAX_LENGTH - 1] + "…"
    return summary
