from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock


class ArtifactProposalConflict(Exception):
    """이미 결정된 변경안이 같은 멱등 키를 쓰고 있음을 알린다."""


class ProposalAlreadyDecided(Exception):
    """결정을 쓰려던 변경안이 이미 결정된 상태였음을 알린다.

    `ArtifactProposalConflict`와 다른 일이다. 그쪽은 새 변경안이 남의
    멱등 키를 밟는 일이고, 이쪽은 두 검토자의 결정이 같은 행을 두고
    부딪히는 일이다. 하나로 합치면 호출자가 둘을 가려 다룰 수 없다.
    """


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
        origin: 이 변경안이 어디서 왔는지 나타낸다. 검토 큐가 컴파일러가
            만든 안건과 사람이 올린 안건을 가려 보여 주는 재료다.
        created_at: 변경안이 올라온 시각을 나타낸다. 검토 큐의 정렬
            기준이므로 목록을 읽는 쪽이 함께 받아야 한다.
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
    origin: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CurrentRevisionForProjection:
    """검색 projection이 읽는 current revision 한 판을 담는다.

    current revision은 컬럼이 아니라 계산값이다. 문서마다 판 번호가 가장
    큰 한 판이 지금 발행된 내용이므로, 이 값 객체도 문서당 한 건만 나온다.

    Attributes:
        artifact_id: 이 판이 속한 문서를 가리킨다.
        title: 문서 제목을 보존한다.
        revision_id: 이 판을 가리킨다.
        revision_number: 판 번호를 나타낸다.
        blocks: 판 본문을 도메인 블록으로 담는다.
        created_at: 판이 발행된 시각을 나타낸다.
    """

    artifact_id: uuid.UUID
    title: str
    revision_id: uuid.UUID
    revision_number: int
    blocks: tuple[ArtifactBlock, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EntityCardSource:
    """카드를 만들 대상 노드 하나를 담는다.

    Attributes:
        node_id: 대상 canonical 노드를 가리킨다.
        display_name: 문서 제목으로 쓸 이름을 담는다.
    """

    node_id: uuid.UUID
    display_name: str


class ArtifactRepository(Protocol):
    """문서와 변경안과 판의 영속성 기능을 정의한다.

    workspace 범위는 저장소를 만들 때 정해진다. 문서 하나를 다루는 동안
    메서드마다 같은 workspace를 다시 넘기게 하면 호출자가 그것을 틀릴
    자리가 생기기 때문이다.
    """

    def find_entity_nodes_by_types(
        self,
        *,
        entity_types: Sequence[str],
    ) -> list[EntityCardSource]:
        """고른 종류의 살아 있는(active) entity 노드를 모두 돌려준다.

        정의가 고른 종류에 해당하면 전부 대상이다. claim이 몇 건인지는
        보지 않는다 — 정의는 조건이지 인기 순위가 아니므로, claim이 쌓이는
        속도에 따라 어떤 노드가 문서가 되는지 달라지면 안 된다.

        차례는 이름·식별자 사전순이다. 같은 지식 상태에서 두 번 물으면
        같은 목록이 나와야 검토 큐에 오르는 순서가 흔들리지 않는다.
        """
        ...

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

        찾는 기준은 (정의, 대상) 하나뿐이다. 그 짝이 유일하다는 것이
        저장 계층의 제약이므로, kind나 채널을 조건에 더하면 정의가
        바뀐 뒤 같은 짝의 문서를 새로 만들어 문서가 갈라진다.

        이미 있으면 제목을 덮어쓰지 않는다. 제목은 문서의 정체성이라
        컴파일을 다시 돌 때마다 바뀌면 사람이 같은 문서인지 알 수 없다.

        채널과 kind는 정의에서 그대로 이어받아 새 행에만 적는다. 문서가
        딛고 선 정의와 같은 채널·kind임을 저장 계층이 보증하기 때문이다.

        folder_id도 새 행에만 적는다. 이미 있는 문서의 폴더는 덮어쓰지
        않는다. 폴더 이동은 사람의 결정이다.
        """
        ...

    def find_definition_artifact(
        self,
        *,
        definition_id: uuid.UUID,
        subject_node_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """정의가 대상에 만든 문서를 찾기만 한다. 없으면 None이다.

        찾는 기준은 `get_or_create_definition_artifact`와 같은 (정의,
        대상)이다. 다른 기준을 쓰면 같은 짝을 두 함수가 다르게 가리켜,
        한쪽이 만든 문서를 다른 쪽이 못 찾는다.

        만들지 않는 것이 이 함수의 존재 이유다. 문서를 세울 수 없다고
        판정한 자리에서 예전 변경안을 거두려면 문서를 먼저 찾아야 하는데,
        그때 없는 문서를 새로 만들면 제목만 있고 내용이 없는 카드가 선다.
        """
        ...

    def find_latest_revision_id_and_number(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> tuple[uuid.UUID, int] | None:
        """문서의 가장 최근 판을 식별자와 번호로 돌려준다."""
        ...

    def find_current_revisions(
        self, *, workspace_id: int
    ) -> tuple[CurrentRevisionForProjection, ...]:
        """workspace의 모든 문서에서 current revision을 한 번에 읽는다.

        검색 인덱스는 원장에서 다시 만들 수 있는 projection이므로,
        재투영은 지금 발행된 판 전부를 훑어야 한다. 문서마다 따로 묻는
        대신 한 질의로 모아 읽는다. 판이 하나도 없는 문서는 아직 사람
        앞에 놓인 내용이 없으므로 빠진다.

        workspace를 명시로 받는다. 저장소가 고정한 workspace와 다르면
        재투영이 남의 문서를 실을 자리이므로, 어긋나면 막는다.

        Raises:
            ValueError: 저장소가 고정한 workspace와 다를 때 던진다.
        """
        ...

    def list_reusable_narratives(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> dict[str, str]:
        """다시 쓸 수 있는 산문을 블록 지문으로 찾아 모은다.

        재료는 최신 발행 판과 계류 중인 변경안뿐이다. 반려된 변경안의
        산문은 사람이 그 문장을 물린 것이므로 넣지 않고, 접힌 변경안은
        이미 대체된 내용이라 넣지 않는다.

        키가 블록 지문인 것이 요점이다. 지문은 산문을 빼고 계산하므로,
        내용이 그대로인 블록은 지난번 문장을 바이트 그대로 다시 쓴다.
        그래야 한 블록의 변화가 문서 전체의 산문을 흔들지 않는다.
        """
        ...

    def find_latest_revision_blocks(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> tuple[ArtifactBlock, ...] | None:
        """최신 발행 판의 블록을 돌려준다. 발행 판이 없으면 None이다.

        무엇이 바뀌었는지 말하려면 비교할 이전 내용이 있어야 한다. 판이
        없다는 것은 아직 사람 앞에 놓인 내용이 없다는 뜻이므로, 빈 튜플이
        아니라 None으로 알린다. 빈 튜플이면 "블록이 하나도 없는 판"과
        구분되지 않는다.
        """
        ...

    def list_reusable_change_reasons(
        self,
        *,
        artifact_id: uuid.UUID,
        base_revision_id: uuid.UUID,
    ) -> dict[str, str]:
        """같은 기준 판 위에 선 계류 변경안에서 수정 이유를 모아 온다.

        키는 블록 내용 지문이고 값은 그 블록에 붙어 있던 수정 이유다.
        기준 판이 같으면 짝지을 이전 블록도 같으므로, 이전 블록과 새 블록
        두 지문을 짝으로 들고 다니지 않고 새 블록 지문 하나만 키로 쓴다.

        반려된 변경안의 이유는 넣지 않는다. 사람이 그 변경안을 물렸으므로
        거기 붙은 문장도 다시 쓸 것이 아니다.
        """
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

    def abandon_pending_proposals(
        self,
        *,
        artifact_id: uuid.UUID,
        except_content_hash: str | None = None,
    ) -> int:
        """문서의 계류안을 접되 지정한 현재 내용은 남긴다."""
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

        저장 직전에 문서의 최신 판이 `base_revision_id`와 같은지 확인한다.
        호출자가 기준 판을 읽은 뒤 여기 도착하기까지 사이에 다른 검토가
        새 판을 냈으면 낡은 기준의 계류가 되므로, 저장하지 않고 예외로
        알린다. 구현은 이 확인과 저장을 문서 행 잠금 아래에서 한 묶음으로
        해야 한다.

        Raises:
            ArtifactBlockError: 블록이 근거 계약을 어겼을 때 던진다.
            ArtifactProposalConflict: 같은 키를 이미 결정된 변경안이 쓰고
                있거나, 기준 판이 최신이 아닐 때 던진다.
        """
        ...

    def get_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
        for_update: bool = False,
    ) -> StoredArtifactProposal | None:
        """변경안 하나를 문서 제목·대상과 함께 읽는다.

        for_update가 참이면 변경안 행을 transaction이 끝날 때까지 잠근다.
        같은 변경안을 건드리는 단건 판정과 일괄 발행이 이 행 하나를 두고
        줄을 서므로, 한쪽이 읽은 결정 목록이 다른 쪽 때문에 도중에 바뀌지
        않는다. 구현은 그 변경안이 달린 문서 행을 함께, 그리고 변경안
        행보다 먼저 잠가야 한다. 판을 쌓는 자리와 변경안을 저장하는
        자리가 문서 행 하나로 줄을 서기 때문이다.
        """
        ...

    def list_pending_proposals(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StoredArtifactProposal]:
        """검토를 기다리는 변경안을 오래된 순으로 읽는다.

        limit/offset은 그 오래된 순 위에서 자른다. 다른 순서로 보여 주는
        호출자는 여기서 자르면 안 된다 — 자기 정렬이 페이지 경계를 넘어
        섞이기 때문이다. limit이 None이면 전부 읽는다.
        """
        ...

    def mark_approved(self, *, proposal_id: uuid.UUID, reviewer: str) -> None:
        """아직 계류 중인 변경안을 승인으로 끝맺는다.

        계류 중인 행만 바꾼다. 두 검토자가 같은 변경안을 동시에 열면
        둘 다 계류로 읽으므로, 상태 검사만으로는 나중 쓰기가 먼저
        확정된 결정을 덮는다. 그 전이를 쓰기 자체의 조건으로 옮겨
        한 행에 결정이 한 번만 실리게 한다.

        Raises:
            ProposalAlreadyDecided: 바꿀 계류 행이 없을 때 던진다.
        """
        ...

    def mark_rejected(
        self,
        *,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        """아직 계류 중인 변경안을 사유와 함께 반려로 끝맺는다.

        `mark_approved`와 같이 계류 중인 행만 바꾼다.

        Raises:
            ProposalAlreadyDecided: 바꿀 계류 행이 없을 때 던진다.
        """
        ...

    def add_revision(
        self,
        *,
        artifact_id: uuid.UUID,
        revision_number: int,
        blocks: Sequence[ArtifactBlock],
        source_proposal_id: uuid.UUID,
    ) -> uuid.UUID:
        """승인으로 확정된 판을 새로 쌓는다.

        구현은 변경안 저장과 같은 문서 행 잠금 아래에서 쌓아야 한다.
        그래야 변경안을 저장하는 쪽이 기준 판을 확인하는 동안 새 판이
        끼어들지 않는다.
        """
        ...
