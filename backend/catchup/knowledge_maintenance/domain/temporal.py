"""claim 유효 구간의 단일 정의다.

"T 시점에 참인가"의 답은 이 함수 하나가 정한다. 구간은 [valid_from,
valid_to) 반개구간이고, 시작 미상(valid_from None)은 포함한다 —
확실성 구분은 소비자가 valid_from 값으로 한다. SQL reader의 as-of
조건은 이 정의와 동일해야 한다.
"""

from __future__ import annotations

from datetime import datetime


def claim_valid_at(
    valid_from: datetime | None,
    valid_to: datetime | None,
    at: datetime,
) -> bool:
    """claim이 at 시점에 참인 구간 안에 있는지 판정한다."""
    if valid_from is not None and valid_from > at:
        return False
    if valid_to is not None and valid_to <= at:
        return False
    return True


def claim_not_closed_at(
    valid_to: datetime | None,
    at: datetime,
) -> bool:
    """claim이 at 시점 기준으로 아직 닫히지 않았는지 판정한다.

    valid_from은 보지 않는다 — 감지기와 컴파일러는 "닫힌 주장 제외"
    의미론을 쓴다. 발효 예정(valid_from이 미래) claim을 현재 판정에
    넣을지는 별도 결정 사항이라 as-of 조회(claim_valid_at)와 의미를
    분리한다.
    """
    return valid_to is None or valid_to > at
