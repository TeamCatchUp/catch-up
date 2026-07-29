from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

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
    """같은 이름 그룹이 같은 대상인지 판정하는 기능을 정의한다.

    sync로 정의한다. LLM 어댑터가 내부에서 비동기 호출을 감싸며,
    서비스와 러너는 이벤트 루프를 몰라도 된다.
    """

    def judge(
        self,
        group: tuple[JudgeCandidate, ...],
    ) -> IdentityVerdict: ...
