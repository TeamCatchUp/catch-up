"""블록 변경 이유가 LLM과 주고받는 계약을 정의한다.

받을 것이 문장 하나뿐이라 칸도 하나다. 그래도 구조화 출력으로 받는
이유는, 자유 문자열로 받으면 모델이 머리말이나 목록 기호를 붙여도
그것을 걸러 낼 자리가 없기 때문이다.

문서 산문의 응답 계약은 여기 두지 않는다. 그 계약은 문서 한 번의 응답
모양이라 어댑터 안에서만 쓰이고, 어댑터가 곧바로 도메인 자료형으로
옮겨 내보낸다.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class ChangeReasonContract(BaseModel):
    """바뀐 블록 하나의 수정 이유 한 문장을 담는다.

    Attributes:
        reason: 왜 이 블록이 바뀌었는지 알리는 한 문장을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    reason: str
