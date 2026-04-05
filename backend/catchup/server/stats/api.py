import structlog
from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.costs.dependencies import CostQueryParam
from catchup.costs.dependencies import cost_query_params
from catchup.costs.service import calculate_chat_token_cost
from catchup.db.costs import get_user_chat_token_usage_by_model
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.server.stats.schemas import UserChatTokenUsageResponse

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/stats",
    tags=["Stats"]
)


@router.get(
    path="/costs/tokens/me",
    response_model=UserChatTokenUsageResponse,
    description="로그인한 사용자 본인의 채팅 토큰 사용량을 USD로 반환한다."
)
def get_my_chat_token_cost_usd(
    params: CostQueryParam = Depends(cost_query_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    usages = get_user_chat_token_usage_by_model(
        db=db,
        user_id=current_user.id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_chat_token_cost(usages)
    return {
        **result,
        "start_date": params.start_date,
        "end_date": params.end_date
    }
