import structlog
from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.costs.service import calculate_chat_token_cost
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.server.dependencies import DateRangeQueryParam
from catchup.server.dependencies import date_range_query_params
from catchup.server.stats.schemas import ChatTokenUsageResponse

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/stats",
    tags=["Stats"]
)


@router.get(
    path="/costs/tokens/me",
    response_model=ChatTokenUsageResponse,
    description="로그인한 사용자 본인의 일자별 채팅 토큰 사용량을 USD로 반환한다."
)
def get_my_chat_token_cost_usd(
    params: DateRangeQueryParam = Depends(date_range_query_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    result = calculate_chat_token_cost(
        db=db,
        user_id=current_user.id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    logger.info(
        "chat_token_cost_queried",
        user_id=current_user.id,
        total_usd=result["total_usd"],
        start_date=params.start_date.isoformat(),
        end_date=params.end_date.isoformat(),
    )
    return {
        **result,
        "start_date": params.start_date,
        "end_date": params.end_date,
    }
