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


@dataclass(frozen=True, slots=True)
class BlockNarrationInput:
    """문서 서술 요청에 실리는 블록 하나의 재료를 담는다.

    블록 하나만 담는다는 점에서 NarrationRequest와 같지만, 문체 지시와
    문서 목적은 담지 않는다. 그 둘은 문서 전체에 한 번만 실리므로
    DocumentNarrationRequest가 가진다.

    Attributes:
        block_id: 요청 안에서의 위치 번호를 담는다. 응답은 이 번호로
            산문을 돌려주므로, 어느 산문이 어느 블록의 것인지 이 번호로만
            정해진다.
        block_kind: 블록 종류를 나타낸다.
        heading: 블록 제목을 담는다. 무엇에 관한 블록인지 알리는 힌트다.
        topic_hint: 컴파일이 만든 본문을 담는다. 색인용 라벨에서 온
            문장이라 근거가 아니라 주제 힌트다.
        statements: 검증된 인용 원문을 담는다.
        edges: 관계 절의 간선 줄을 담는다. 관계 절이 아닌 블록에서는
            비어 있다.
        hints: 관계에 붙은 원문 유래 문장을 담는다. 사실 입력이 아니라
            표현 힌트다.
        variants: 대조 후보를 (후보 본문, 그 후보의 인용들)로 담는다.
    """

    block_id: int
    block_kind: str
    heading: str
    topic_hint: str
    statements: tuple[str, ...]
    edges: tuple[str, ...]
    hints: tuple[str, ...]
    variants: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True, slots=True)
class DocumentNarrationRequest:
    """문서 하나의 산문을 한 번에 받아 오는 데 필요한 재료를 담는다.

    블록마다 따로 묻지 않고 문서 단위로 한 번만 묻는다. 문체 지시와 문서
    목적이 블록 수만큼 되풀이되지 않고, 같은 문서의 블록들이 서로의 문장을
    보고 쓸 수 있다.

    Attributes:
        style_instruction: 어떤 문체로 쓸지 알리는 지시 한 문단이다.
        purpose_sentence: 이 문서가 무엇에 쓰이는지 알리는 한 줄이다.
        summary: 머리말 세 칸을 쓰는 데 필요한 재료를 담는다. 머리말이
            필요 없으면 None이다. 머리말의 근거는 문서 전체의 검증된
            인용이다.
        blocks: 산문이 필요한 섹션 블록만 담는다. 앞 버전의 산문을 그대로
            쓰는 블록은 담지 않는다.
    """

    style_instruction: str
    purpose_sentence: str
    summary: BlockNarrationInput | None
    blocks: tuple[BlockNarrationInput, ...]


@dataclass(frozen=True, slots=True)
class SummaryNarrative:
    """문서 머리말을 이루는 세 칸을 담는다.

    머리말은 한 덩어리 문장이 아니라 정해진 세 칸으로 읽힌다. 자유
    문자열 하나로 돌려주면 어느 문장이 어느 칸인지 밖에서 알 수 없어,
    받는 자리에서 칸을 갈라 둔다.

    Attributes:
        one_line_summary: 누가 무엇을 하고 싶어 하는지 한 문장으로 담는다.
            이 문장만 읽어도 요구가 무엇인지 알 수 있어야 한다.
        desired_outcome: 고객이 얻고자 하는 최종 결과를 담는다. 무엇을
            어떻게 만들지가 아니라 결과만 적는다.
        background: 요청이 나온 이유와 지금 어떻게 일하고 있는지를 담는다.
            고객이 말한 사실만 적는다.
    """

    one_line_summary: str
    desired_outcome: str
    background: str


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
    """블록 하나를 산문 한 문단으로 옮기는 기능을 정의한다."""

    def narrate(self, request: NarrationRequest) -> str:
        """재료를 주고 산문 한 문단을 받는다.

        빈 문장을 성공으로 돌려주지 않는다. 근거가 있는데 문장이 비면
        그것은 서술 실패이고, 근거가 없는 블록은 애초에 부르지 않는다.

        Raises:
            NarrationError: 산문을 받아 오지 못했을 때 던진다.
        """
        ...

    def narrate_summary(self, request: NarrationRequest) -> SummaryNarrative:
        """문서 머리말을 정해진 세 칸으로 받는다.

        머리말은 본문 블록과 달리 칸이 정해져 있다. 한 줄 요약은 누가
        무엇을 하고 싶어 하는지 한 문장으로 적고, 그 문장만 읽어도 요구를
        알 수 있어야 한다. 원하는 결과는 구현 방식이 아니라 고객이 얻고자
        하는 최종 결과를 적는다. 요청 배경은 요청이 나온 이유와 지금의
        업무 방식을 고객이 말한 사실만으로 적는다.

        세 칸 중 하나라도 비면 성공이 아니다. 칸이 빈 머리말은 화면에서
        제목만 남은 빈 칸으로 그려지므로 문서 하나를 접는 편이 낫다.

        Raises:
            NarrationError: 머리말을 받아 오지 못했거나 어느 칸이든
                비었을 때 던진다.
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
