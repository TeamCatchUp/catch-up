from datetime import UTC
from datetime import datetime
from datetime import timedelta

from attr import dataclass
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

# 집계 조회 최대 기간
# TODO: 서비스 이용 시작 기간 이래로 무제한 가능
MAX_RANGE_DAYS = 365 * 3

@dataclass
class DateRangeQueryParam:
    start_date: datetime
    end_date: datetime


def date_range_query_params(
    start_date: datetime = Query(
        description="집계 시작 날짜 (ISO 8601, UTC)",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="집계 종료 날짜 (ISO 8601, UTC). 없으면 현재 시간 기준.",
    ),
) -> DateRangeQueryParam:
    resolved_end = (
        end_date + timedelta(days=1)
        if end_date
        else datetime.now(UTC)
    )

    if (resolved_end - start_date).days > MAX_RANGE_DAYS:
        # TODO: OutOfQueryRangeError 커스텀 예외 대체
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"최대 조회 범위는 {MAX_RANGE_DAYS // 365}년입니다."
        )

    return DateRangeQueryParam(start_date=start_date, end_date=resolved_end)