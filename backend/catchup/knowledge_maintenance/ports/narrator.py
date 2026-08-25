"""문서 산문을 받아 오는 포트를 정의한다.

컴파일은 블록을 결정론으로 만들고, 그 위에 얹을 문장만 밖에서 받는다.
산문은 근거가 아니라 표현이므로 이 포트를 거쳐 들어온 값은 블록의 내용
지문에 끼지 않는다.

요청·응답 자료형은 domain/narration_contract.py에 있고 여기서 가져다
쓴다. 검사기가 그 모양을 알아야 하는데 포트에 두면 도메인이 포트를 향하게
되기 때문이다. 기존 호출부가 쓰던 이름은 여기서 그대로 쓸 수 있게
다시 내보낸다.

부재를 표현하는 널 구현을 두지 않는다. narrator가 없다는 것과 그 블록에
산문이 없다는 것은 둘 다 None으로 말하는 편이 호출부에서 읽기 쉽다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.narration_contract import BlockNarrationInput
from catchup.knowledge_maintenance.domain.narration_contract import (
    DocumentNarrationRequest,
)
from catchup.knowledge_maintenance.domain.narration_contract import SummaryNarrative

__all__ = [
    "BlockNarrationInput",
    "BlockNarrator",
    "ChangeExplanationRequest",
    "DocumentNarration",
    "DocumentNarrationRequest",
    "NarrationError",
    "SummaryNarrative",
]


class NarrationError(RuntimeError):
    """문서 산문을 받아 오지 못했음을 알린다.

    호출자는 이 예외를 문서 하나를 접는 신호로 읽는다. 산문이 반쪽인
    문서를 검수자에게 올리지 않는 것이 이 예외의 존재 이유다.
    """


@dataclass(frozen=True, slots=True)
class DocumentNarration:
    """문서 서술 한 번의 결과를 담는다.

    Attributes:
        summary: 받아 온 머리말 세 칸을 담는다. 머리말을 묻지 않았으면
            None이다.
        narratives: 블록 번호를 산문에 짝지어 담는다. 검증을 통과한 값만
            담긴다.
    """

    summary: SummaryNarrative | None
    narratives: Mapping[int, str]


@dataclass(frozen=True, slots=True)
class ChangeExplanationRequest:
    """바뀐 블록 하나의 수정 이유를 묻는 데 필요한 재료를 담는다.

    문서를 다시 여는 사람이 가장 먼저 묻는 것은 "무엇이 달라졌나"가 아니라
    "왜 달라졌나"다. 앞뒤 문장과 새로 붙은 인용만 주면 그 답을 쓸 수 있고,
    제안 id나 검수자 같은 운영 정보는 답에 필요하지 않아 아예 주지 않는다.

    문서 문체 지시는 받지 않는다. 수정 이유는 위키 본문 산문이 아니라
    검토 화면에 붙는 안내 문구이고, 검토자에게 말을 거는 자리라 문서가
    어떤 문체를 쓰든 존댓말로 쓴다. 문서 문체 preset은 본문 산문에만
    적용한다.

    Attributes:
        heading: 바뀐 블록의 제목을 담는다.
        before_statements: 바뀌기 전 블록이 담고 있던 문장을 담는다.
        after_statements: 바뀐 뒤 블록이 담고 있는 문장을 담는다.
        new_sources: 이번에 새로 붙은 검증된 인용 원문을 담는다. 무엇이
            변경을 불러왔는지 말할 수 있는 유일한 근거다.
        purpose_sentence: 이 문서가 무엇에 쓰이는지 알리는 한 줄이다.
    """

    heading: str
    before_statements: tuple[str, ...]
    after_statements: tuple[str, ...]
    new_sources: tuple[str, ...]
    purpose_sentence: str


class BlockNarrator(Protocol):
    """문서 하나의 산문을 받아 오는 기능을 정의한다."""

    def narrate_document(
        self, request: DocumentNarrationRequest
    ) -> DocumentNarration:
        """문서 하나의 산문을 한 번에 받는다.

        블록마다 따로 묻지 않는다. 한 번에 물으면 문체 지시와 문서 목적을
        되풀이하지 않아도 되고, 같은 문서의 블록들이 서로의 문장을 보고
        쓸 수 있다.

        받아 온 값은 그대로 믿지 않는다. 결정론 검사기에 걸어 위반이
        있으면 위반 블록만 한 번 다시 묻는다. 돌려주는 narratives에는
        검증을 통과한 값만 담긴다.

        Raises:
            NarrationError: 프롬프트를 만들지 못했거나 호출이 터졌거나
                계약이 깨졌거나, 다시 물어도 검증 위반이 남았을 때 던진다.
        """
        ...

    def explain_change(self, request: ChangeExplanationRequest) -> str:
        """바뀐 블록의 수정 이유 한 문장을 받는다.

        산문과 마찬가지로 빈 문장을 성공으로 돌려주지 않는다. 바뀐 것이
        없는 블록은 애초에 부르지 않는다.

        돌려주는 문장은 존댓말이다. 수정 이유는 검토 화면에 붙는 안내
        문구라서 문서 본문 문체를 따르지 않고, 문서가 어떤 문체를 쓰든
        검토자에게 존댓말로 말한다.

        Raises:
            NarrationError: 이유를 받아 오지 못했을 때 던진다.
        """
        ...
