from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Locator:
    """근거 문구가 본문 어디에 있는지, 그리고 언제 말해졌는지 가리킨다.

    offset은 Unicode code point 단위다. Python 문자열 인덱스와 같고,
    UTF-16 code unit(JavaScript 문자열 인덱스)과는 다르다. 이모지처럼
    UTF-16에서 두 칸인 문자도 여기서는 한 칸이다. UTF-16이 필요한 소비자는
    읽기 시점에 변환한다.

    `event_at`은 그 위치의 발화가 일어난 시각을 ISO 8601 문자열로 담는다.
    "어디서"의 기록에 "언제"를 함께 두는 이유는 둘이 같은 발화를 가리키기
    때문이다. 문서 하나에 시각을 하나만 두면 여러 날에 걸친 상담에서 뒷날
    발화가 상담 시작 시각으로 앵커되어 주장 사이의 선후가 뒤집힌다. 발화
    시각을 모르면 비운다 — 소비자는 문서 단위 사슬로 물러난다.

    Attributes:
        kind: offset의 단위 계약을 나타낸다.
        start: 근거 문구가 시작하는 offset을 나타낸다.
        end: 근거 문구가 끝나는 offset을 나타낸다.
        event_at: 그 위치의 발화 시각을 ISO 8601 문자열로 담는다.
    """

    kind: str
    start: int
    end: int
    event_at: str | None = None


def locate_excerpt(content: str | None, statement: str) -> Locator | None:
    """statement가 content에 정확히 한 번 나오면 그 위치를 돌려준다.

    없거나 여러 번 나오면 None을 돌려주고, 호출자는 evidence를 위치 없는
    문서 단위 근거로 낮춘다. 저장된 evidence에서 locator가 비어 있다는
    것은 인용이 원문 대조를 통과하지 못했다는 뜻이며, 소비자는 빈
    locator의 excerpt를 검증된 인용으로 취급하면 안 된다.
    """
    if content is None:
        return None
    index = content.find(statement)
    if index == -1:
        return None
    if content.find(statement, index + 1) != -1:
        return None
    return Locator(
        kind="codepoint_offset",
        start=index,
        end=index + len(statement),
    )
