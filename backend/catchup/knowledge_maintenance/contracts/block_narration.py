"""블록 서술이 LLM과 주고받는 계약을 정의한다.

받을 것이 문단 하나뿐이라 칸도 하나다. 그래도 구조화 출력으로 받는
이유는, 자유 문자열로 받으면 모델이 머리말이나 목록 기호를 붙여도
그것을 걸러 낼 자리가 없기 때문이다.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class NarrativeContract(BaseModel):
    """블록 하나에 붙일 산문 한 문단을 담는다.

    Attributes:
        narrative: 사람이 읽을 산문 본문을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    narrative: str
