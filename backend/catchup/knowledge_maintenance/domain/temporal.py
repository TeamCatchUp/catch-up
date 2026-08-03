"""claim 시간축의 단일 정의다 — 유효 구간과 기준 시각을 함께 정한다.

"T 시점에 참인가"의 답은 이 함수 하나가 정한다. 구간은 [valid_from,
valid_to) 반개구간이고, 시작 미상(valid_from None)은 포함한다 —
확실성 구분은 소비자가 valid_from 값으로 한다. SQL reader의 as-of
조건은 이 정의와 동일해야 한다.

"문서를 읽을 때의 지금은 언제인가"도 여기서 정한다
(resolve_reference_time). 추출이 쓰는 기준 시각과 reader가 공급하는
관찰 시각이 같은 사슬을 타야 하기 때문이다.
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


def resolve_reference_time(
    *,
    occurred_at: datetime | None,
    source_updated_at: datetime | None,
    observed_at: datetime,
) -> tuple[datetime, str]:
    """문서의 기준 시각과 그 출처를 정한다.

    기준 시각은 문서 안의 시간 표현을 해석할 때 "지금"으로 삼는
    시각이다. 원천 사건 시각(occurred_at)이 최선이고, 없으면 원문
    변경 시각, 그것도 없으면 수집 시각으로 내려간다 — Graphiti
    reference_time 방식이다. 어느 단계가 쓰였는지가 품질 추적의
    재료이므로 출처를 함께 돌려준다. reader의 SQL coalesce
    (find_claim_candidates)와 같은 사슬이어야 한다.
    """
    if occurred_at is not None:
        return occurred_at, "occurred_at"
    if source_updated_at is not None:
        return source_updated_at, "source_updated_at"
    return observed_at, "observed_at"
