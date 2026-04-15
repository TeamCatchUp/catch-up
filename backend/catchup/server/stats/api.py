import structlog
from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.auth.dependencies import require_admin_user
from catchup.costs.service import calculate_chat_token_cost
from catchup.costs.service import calculate_question_count
from catchup.costs.service import calculate_user_token_cost_ranking
from catchup.db.chat_room import get_org_question_count_by_range
from catchup.db.chat_room import get_user_question_count_by_range
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.token_usages import get_org_chat_token_usage_by_range
from catchup.db.token_usages import get_user_chat_token_usage_by_range
from catchup.db.token_usages import get_user_token_usage_ranking
from catchup.server.dependencies import DateRangeQueryParam
from catchup.server.dependencies import date_range_query_params
from catchup.server.stats.schemas import ChatTokenUsageResponse
from catchup.server.stats.schemas import QuestionCountResponse
from catchup.server.stats.schemas import UserTokenCostRankingResponse

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
    usages = get_user_chat_token_usage_by_range(
        db=db,
        user_id=current_user.id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_chat_token_cost(
        usages=usages,
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


@router.get(
    path="/costs/tokens/org",
    response_model=ChatTokenUsageResponse,
    description="조직의 일자별 토큰 사용량을 USD로 반환한다."
)
def get_org_chat_token_cost_usd(
    params: DateRangeQueryParam = Depends(date_range_query_params),
    _require_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    usages = get_org_chat_token_usage_by_range(
        db=db,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_chat_token_cost(
        usages=usages,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    logger.info(
        "chat_token_cost_queried",
        total_usd=result["total_usd"],
        start_date=params.start_date.isoformat(),
        end_date=params.end_date.isoformat(),
    )
    return {
        **result,
        "start_date": params.start_date,
        "end_date": params.end_date,
    }


@router.get(
    path="/costs/tokens/ranking",
    response_model=UserTokenCostRankingResponse,
    description="기간 내 구성원별 토큰 사용량을 USD 내림차순으로 반환한다."
)
def get_user_token_cost_ranking(
    params: DateRangeQueryParam = Depends(date_range_query_params),
    _require_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    rows = get_user_token_usage_ranking(
        db=db,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    ranking = calculate_user_token_cost_ranking(rows)
    return {
        "ranking": ranking,
        "start_date": params.start_date,
        "end_date": params.end_date,
    }


@router.get(
    path="/costs/tokens/users/{user_id}",
    response_model=ChatTokenUsageResponse,
    description="특정 구성원의 일자별 채팅 토큰 사용량을 USD로 반환한다."
)
def get_user_chat_token_cost_by_id(
    user_id: int,
    params: DateRangeQueryParam = Depends(date_range_query_params),
    _require_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    usages = get_user_chat_token_usage_by_range(
        db=db,
        user_id=user_id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_chat_token_cost(
        usages=usages,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    return {
        **result,
        "start_date": params.start_date,
        "end_date": params.end_date,
    }


@router.get(
    path="/queries/me",
    response_model=QuestionCountResponse,
    description="로그인한 사용자 본인의 일자별 질문 횟수를 반환한다."
)
def get_my_question_count(
    params: DateRangeQueryParam = Depends(date_range_query_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    counts = get_user_question_count_by_range(
        db=db,
        user_id=current_user.id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_question_count(
        counts=counts,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    return {**result, "start_date": params.start_date, "end_date": params.end_date}


@router.get(
    path="/queries/org",
    response_model=QuestionCountResponse,
    description="조직 전체의 일자별 질문 횟수를 반환한다."
)
def get_org_question_count(
    params: DateRangeQueryParam = Depends(date_range_query_params),
    _require_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    counts = get_org_question_count_by_range(
        db=db,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_question_count(
        counts=counts,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    return {**result, "start_date": params.start_date, "end_date": params.end_date}


@router.get(
    path="/queries/users/{user_id}",
    response_model=QuestionCountResponse,
    description="특정 구성원의 일자별 질문 횟수를 반환한다."
)
def get_user_question_count_by_id(
    user_id: int,
    params: DateRangeQueryParam = Depends(date_range_query_params),
    _require_admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    counts = get_user_question_count_by_range(
        db=db,
        user_id=user_id,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    result = calculate_question_count(
        counts=counts,
        start_date=params.start_date,
        end_date=params.end_date,
    )
    return {**result, "start_date": params.start_date, "end_date": params.end_date}
