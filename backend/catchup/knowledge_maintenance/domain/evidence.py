from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Locator:
    """근거 문구가 본문 어디에 있는지 문자 단위로 가리킨다."""

    kind: str
    start: int
    end: int


def locate_excerpt(content: str | None, statement: str) -> Locator | None:
    """statement가 content에 정확히 한 번 나오면 그 위치를 돌려준다."""
    if content is None:
        return None
    index = content.find(statement)
    if index == -1:
        return None
    if content.find(statement, index + 1) != -1:
        return None
    return Locator(kind="char_offset", start=index, end=index + len(statement))
