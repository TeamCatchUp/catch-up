from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock


class ArtifactProposalConflict(Exception):
    """이미 결정된 변경안이 같은 멱등 키를 쓰고 있음을 알린다."""


@dataclass(frozen=True, slots=True)
class StoredArtifactProposal:
    """저장된 문서 변경안 한 건을 검토자가 볼 수 있는 형태로 담는다.

    Attributes:
        id: 변경안 식별자를 나타낸다.
        artifact_id: 이 변경안이 붙은 문서를 가리킨다.
        subject_node_id: 문서가 설명하는 대상 노드를 가리킨다.
        title: 문서 제목을 보존한다.
        status: 검토 상태를 나타낸다.
        blocks: 변경안 본문이자 근거 장부를 담는다.
        content_hash: 본문 내용의 지문을 나타낸다.
        base_revision_id: 이 변경안이 딛고 선 판을 가리킨다.
        rejection_reason: 반려 사유를 보존한다.
    """

    id: uuid.UUID
    artifact_id: uuid.UUID
    subject_node_id: uuid.UUID
    title: str
    status: str
    blocks: tuple[ArtifactBlock, ...]
    content_hash: str
    base_revision_id: uuid.UUID | None
    rejection_reason: str | None


@dataclass(frozen=True, slots=True)
class EntityCardSource:
    """카드를 만들 대상 노드 하나를 담는다.

    Attributes:
        node_id: 대상 canonical 노드를 가리킨다.
        display_name: 문서 제목으로 쓸 이름을 담는다.
        claim_count: 이 노드를 subject로 삼는 claim 수를 나타낸다.
    """

    node_id: uuid.UUID
    display_name: str
    claim_count: int


class ArtifactRepository(Protocol):
    """문서와 변경안과 판의 영속성 기능을 정의한다.

    workspace 범위는 저장소를 만들 때 정해진다. 문서 하나를 다루는 동안
    메서드마다 같은 workspace를 다시 넘기게 하면 호출자가 그것을 틀릴
    자리가 생기기 때문이다.
    """

    def find_top_entity_nodes(self, *, limit: int) -> list[EntityCardSource]:
        """카드를 만들 대상 노드를 claim이 많은 순으로 고른다.

        살아 있는(active) canonical 노드만 본다. claim이 하나도 없는
        노드는 쓸 내용이 없으므로 제외한다.
        """
        ...

    def get_or_create_artifact(
        self,
        *,
        kind: str,
        subject_node_id: uuid.UUID,
        title: str,
    ) -> uuid.UUID:
        """대상에 붙는 문서를 만들거나 이미 있는 것을 돌려준다."""
        ...

    def find_latest_revision_id_and_number(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> tuple[uuid.UUID, int] | None:
        """문서의 가장 최근 판을 식별자와 번호로 돌려준다."""
        ...

    def find_latest_content_hashes(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> set[str]:
        """이미 사람 앞에 놓인 내용의 지문을 모은다.

        최신 판의 지문과 아직 열려 있거나 반려된 변경안의 지문이다. 같은
        내용을 다시 올려도 검토자에게 새로 보여 줄 것이 없으므로, 여기에
        들어 있는 지문이면 무동작으로 넘긴다. 승인된 변경안의 지문은 그
        승인이 만든 판을 거쳐 들어오고, 접힌 변경안은 다시 올릴 수 있어야
        하므로 들어오지 않는다.
        """
        ...

    def abandon_pending_proposals(self, *, artifact_id: uuid.UUID) -> int:
        """문서에 계류 중인 변경안을 모두 접고 접은 수를 돌려준다."""
        ...

    def add_or_revive_proposal(
        self,
        *,
        artifact_id: uuid.UUID,
        blocks: Sequence[ArtifactBlock],
        content_hash: str,
        idempotency_key: str,
        base_revision_id: uuid.UUID | None,
    ) -> uuid.UUID:
        """변경안을 올린다. 아직 결정되지 않은 행이 있으면 되살린다.

        저장 전에 블록의 근거 계약을 검사한다. 근거 없는 문장이 문서에
        실리는 것을 막는 마지막 자리가 저장 계층이기 때문이다.

        되살리는 것은 pending과 abandoned뿐이다. 사람이 이미 승인하거나
        반려한 행을 되살리면 그 결정의 기록이 사라지므로 예외로 알린다.

        Raises:
            ArtifactBlockError: 블록이 근거 계약을 어겼을 때 던진다.
            ArtifactProposalConflict: 같은 키를 이미 결정된 변경안이 쓰고
                있을 때 던진다.
        """
        ...

    def get_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
    ) -> StoredArtifactProposal | None:
        """변경안 하나를 문서 제목·대상과 함께 읽는다."""
        ...

    def list_pending_proposals(self) -> list[StoredArtifactProposal]:
        """검토를 기다리는 변경안을 오래된 순으로 읽는다."""
        ...

    def mark_approved(self, *, proposal_id: uuid.UUID, reviewer: str) -> None:
        """변경안을 승인으로 끝맺는다."""
        ...

    def mark_rejected(
        self,
        *,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        """변경안을 사유와 함께 반려로 끝맺는다."""
        ...

    def add_revision(
        self,
        *,
        artifact_id: uuid.UUID,
        revision_number: int,
        blocks: Sequence[ArtifactBlock],
        source_proposal_id: uuid.UUID,
    ) -> uuid.UUID:
        """승인으로 확정된 판을 새로 쌓는다."""
        ...
