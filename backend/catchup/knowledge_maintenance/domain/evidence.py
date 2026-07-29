from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Locator:
    """근거 문구가 본문 어디에 있는지 가리킨다.

    offset은 Unicode code point 단위다. Python 문자열 인덱스와 같고,
    UTF-16 code unit(JavaScript 문자열 인덱스)과는 다르다. 이모지처럼
    UTF-16에서 두 칸인 문자도 여기서는 한 칸이다. UTF-16이 필요한 소비자는
    읽기 시점에 변환한다.
    """

    kind: str
    start: int
    end: int


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
