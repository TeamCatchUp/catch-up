from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.entity_blocking import EntityBlock
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityPartition
from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict


@dataclass(frozen=True, slots=True)
class JudgeCandidate:
    """판정에 넘길 후보 한 건의 재료를 표현한다.

    Attributes:
        candidate_id: 후보 행을 식별한다.
        proposed_type: 제안된 entity 종류를 나타낸다.
        proposed_name: 제안된 표시 이름을 나타낸다.
        excerpt: 후보가 나온 원문 맥락을 담는다. 없을 수 있다.
    """

    candidate_id: uuid.UUID
    proposed_type: str
    proposed_name: str
    excerpt: str | None = None


class IdentityJudge(Protocol):
    """이름들이 같은 대상인지 판정하는 기능을 정의한다.

    묻는 방식이 둘이다. `judge`는 같은 이름 그룹 하나가 통째로 같은
    대상인지를 예·아니오로 묻고, `partition`은 이름이 서로 다를 수도 있는
    블록 하나를 정체 여러 개로 갈라 달라고 묻는다. 유사도 blocking이
    들어오면 한 블록에 서로 다른 대상이 섞일 수 있어 예·아니오로는 답이
    안 나오기 때문이다. 해소 서비스가 분할 판정으로 옮겨 갈 때까지 둘을
    함께 둔다.

    sync로 정의한다. LLM 어댑터가 내부에서 비동기 호출을 감싸며,
    서비스와 러너는 이벤트 루프를 몰라도 된다.
    """

    def judge(
        self,
        group: tuple[JudgeCandidate, ...],
    ) -> IdentityVerdict: ...

    def partition(self, block: EntityBlock) -> IdentityPartition:
        """블록 하나를 정체 여러 개로 가른다.

        Args:
            block: 함께 판정할 멤버들을 받는다. 후보와 기존 노드 대표가
                섞여 있을 수 있다.

        Returns:
            멤버를 정확히 한 번씩 덮는 그룹들을 돌려준다.

        Raises:
            PartitionContractError: 출력이 계약을 어겼거나 배정이 어긋났을
                때 던진다. 부르는 쪽은 그 블록만 접는다.
        """
        ...
