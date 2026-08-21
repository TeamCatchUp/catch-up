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


class SummaryNarrativeContract(BaseModel):
    """문서 머리말의 세 칸을 담는다.

    본문 산문과 달리 칸을 갈라 받는다. 한 덩어리 문자열로 받으면 어느
    문장이 어느 칸인지 밖에서 되찾을 수 없고, 화면이 칸 제목을 붙여
    그릴 수 없다.

    Attributes:
        one_line_summary: 누가 무엇을 하고 싶어 하는지 한 문장을 담는다.
        desired_outcome: 고객이 얻고자 하는 최종 결과를 담는다.
        background: 요청이 나온 이유와 지금의 업무 방식을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    one_line_summary: str
    desired_outcome: str
    background: str


class ChangeReasonContract(BaseModel):
    """바뀐 블록 하나의 수정 이유 한 문장을 담는다.

    Attributes:
        reason: 왜 이 블록이 바뀌었는지 알리는 한 문장을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    reason: str
