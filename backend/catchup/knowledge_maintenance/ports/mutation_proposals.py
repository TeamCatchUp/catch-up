from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Protocol

from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredMutationProposal,
)
from catchup.knowledge_maintenance.domain.source_version import JsonValue


class MutationProposalRepository(Protocol):
    """mutation proposal의 영속성 기능을 정의한다."""

    def find_pending_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> StoredMutationProposal | None:
        """같은 검토 단위로 이미 열려 있는 proposal을 찾는다."""
        ...

    def abandon(self, *, proposal_id: uuid.UUID) -> None:
        """proposal을 접는다. 멤버가 달라져 낡은 계획서가 됐을 때 쓴다."""
        ...

    def find_pending_duplicate_groups(
        self,
        *,
        workspace_id: int,
    ) -> dict[uuid.UUID, uuid.UUID]:
        """아직 열려 있는 병합 계획서의 멤버를 계획서로 되짚는다.

        entity 후보 하나가 어느 병합 묶음에 속하는지 알아야 아직 노드로
        해소되지 않은 후보들도 같은 대상으로 묶어 주장을 비교할 수 있다.
        """
        ...

    def find_pending_contradiction_proposals(
        self,
        *,
        workspace_id: int,
    ) -> tuple[tuple[uuid.UUID, str, str | None], ...]:
        """열려 있는 모순 계획서를 식별자·key·predicate로 되짚는다.

        모순은 사라질 수 있다. 값이 한 종으로 수렴하거나 근거 claim이
        없어지거나 subject가 다른 키로 이주하면 옛 계획서는 더 이상
        사실이 아니다. 이번 실행이 확인한 key와 견주어 회수하려면 열려
        있는 목록을 통째로 읽어야 한다.

        predicate를 함께 준다. key만으로는 "모순이 사라졌다"와 "사전이
        더 이상 그 속성을 비교하지 않는다"를 구분할 수 없는데, 뒤쪽까지
        회수하면 어휘를 되돌리는 순간 검토 큐가 통째로 비기 때문이다.
        낡은 metadata에 predicate가 없으면 None이다.
        """
        ...

    def add_duplicate_proposal(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
        trigger_entity_candidate_id: uuid.UUID,
        detector: str,
        detector_version: str,
        summary: str,
        resolver_metadata: Mapping[str, JsonValue],
        representative_candidate_id: uuid.UUID,
        merge_candidate_ids: tuple[uuid.UUID, ...],
        proposed_type: str,
        proposed_name: str,
    ) -> uuid.UUID:
        """같은 대상 후보들을 하나로 합치는 계획서를 쓴다.

        operation은 두 종류다. 대표 후보의 create_entity가 1번이고,
        나머지 후보의 merge_entity가 그 뒤를 따르며 1번이 만들 노드를
        가리킨다.
        """
        ...

    def add_contradiction_proposal(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
        trigger_claim_candidate_id: uuid.UUID,
        detector: str,
        detector_version: str,
        summary: str,
        resolver_metadata: Mapping[str, JsonValue],
    ) -> uuid.UUID:
        """같은 대상의 주장끼리 값이 어긋난다는 사실을 계획서로 남긴다.

        operation을 만들지 않는다. 어느 값이 맞는지는 자동으로 정할 수
        없고, 사람이 판단할 때까지 적용 명령을 만들면 안 되기 때문이다.
        """
        ...
