from datetime import UTC
from datetime import datetime

from attr import dataclass
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from catchup.components.aws.cloudwatch import CloudWatchMetrics
from catchup.components.aws.factory import get_cloudwatch_metrics
from catchup.configs.config import settings

# 집계 조회 최대 기간
# TODO: 서비스 이용 시작 기간 이래로 무제한 가능
MAX_RANGE_DAYS = 365 * 3

@dataclass
class CostQueryParam:
    start_date: datetime
    end_date: datetime


def cost_query_params(
    start_date: datetime = Query(
        description="집계 시작 날짜 (ISO 8601)",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="집계 종료 날짜 (ISO 8601). 없으면 현재 시간 기준.",
    ),
) -> CostQueryParam:
    resolved_end = end_date or datetime.now(UTC)
    
    if (resolved_end - start_date).days > MAX_RANGE_DAYS:
        # TODO: OutOfQueryRangeError 도메인 예외 대체
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"최대 조회 범위는 {MAX_RANGE_DAYS // 365}년입니다."
        )
    
    return CostQueryParam(start_date=start_date, end_date=resolved_end)


def cloudwatch_metrics_dependency() -> CloudWatchMetrics:
    return get_cloudwatch_metrics(
        region_name=settings.AWS_EMBEDDING_MODEL_REGION
    )
