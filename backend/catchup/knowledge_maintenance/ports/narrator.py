"""블록 산문을 받아 오는 포트를 정의한다.

컴파일은 블록을 결정론으로 만들고, 그 위에 얹을 문장 하나만 밖에서
받는다. 산문은 근거가 아니라 표현이므로 이 포트를 거쳐 들어온 값은
블록의 내용 지문에 끼지 않는다.

부재를 표현하는 널 구현을 두지 않는다. narrator가 없다는 것과 그 블록에
산문이 없다는 것은 둘 다 None으로 말하는 편이 호출부에서 읽기 쉽다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class NarrationError(RuntimeError):
    """블록 산문을 받아 오지 못했음을 알린다.

    호출자는 이 예외를 문서 하나를 접는 신호로 읽는다. 산문이 반쪽인
    문서를 검수자에게 올리지 않는 것이 이 예외의 존재 이유다.
    """


@dataclass(frozen=True, slots=True)
class NarrationRequest:
    """블록 하나를 서술하는 데 필요한 재료를 담는다.

    Attributes:
        block_kind: 블록 종류를 나타낸다.
        heading: 블록 제목을 담는다. 무엇에 관한 블록인지 알리는 힌트다.
        topic_hint: 컴파일이 만든 본문을 담는다. 색인용 라벨에서 온
            문장이라 근거가 아니라 주제 힌트다.
        statements: 검증된 인용 원문을 담는다. claim 절·열린 질문·대조
            블록에서 산문이 말할 수 있는 사실은 이것뿐이다.
        edges: 관계 절의 간선 줄을 담는다. 양끝 이름을 명시한 줄과 잘린
            걸음을 알리는 줄이며, 관계 절은 인용 대신 이것을 사실 입력으로
            쓴다. 관계 절이 아닌 블록에서는 비어 있다.
        variants: 대조 후보를 (후보 본문, 그 후보의 인용들)로 담는다.
            후보마다 근거가 갈려 있어 한 덩어리로 뭉치면 어느 인용이
            어느 후보의 것인지 사라진다.
        style_instruction: 어떤 문체로 쓸지 알리는 지시 한 문단이다.
        purpose_sentence: 이 문서가 무엇에 쓰이는지 알리는 한 줄이다.
        hints: 관계에 붙은 원문 유래 문장을 담는다. 사실 입력이 아니라
            표현 힌트다 — 그 문장의 화자를 관계의 상대 노드로 읽는
            오해를 막으려면 사실 목록과 자리를 갈라 두어야 한다.
    """

    block_kind: str
    heading: str
    topic_hint: str
    statements: tuple[str, ...]
    edges: tuple[str, ...]
    variants: tuple[tuple[str, tuple[str, ...]], ...]
    style_instruction: str
    purpose_sentence: str
    hints: tuple[str, ...] = ()


class BlockNarrator(Protocol):
    """블록 하나를 산문 한 문단으로 옮기는 기능을 정의한다."""

    def narrate(self, request: NarrationRequest) -> str:
        """재료를 주고 산문 한 문단을 받는다.

        빈 문장을 성공으로 돌려주지 않는다. 근거가 있는데 문장이 비면
        그것은 서술 실패이고, 근거가 없는 블록은 애초에 부르지 않는다.

        Raises:
            NarrationError: 산문을 받아 오지 못했을 때 던진다.
        """
        ...
