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
