import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.concurrency import run_in_threadpool

from catchup.auth.dependencies import require_admin_user
from catchup.components.aws.cloudwatch import CloudWatchMetrics
from catchup.configs.config import settings
from catchup.costs.dependencies import CostQueryParam
from catchup.costs.dependencies import cloudwatch_metrics_dependency
from catchup.costs.dependencies import cost_query_params
from catchup.costs.pricing import TOKEN_PRICING, calc_token_cost
from catchup.costs.schemas import EmbeddingTokenUsageResponse

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/costs",
    tags=["Token Usages"]
)


@router.get(
    path="/tokens/org/embeddings",
    response_model=EmbeddingTokenUsageResponse,
    description="집계 기간 내 조직의 임베딩 토큰 사용량을 USD로 반환한다."
)
async def get_total_input_tokens_for_embeddings(
    params: CostQueryParam = Depends(cost_query_params),
    cw_metrics: CloudWatchMetrics = Depends(cloudwatch_metrics_dependency),
    _require_admin = Depends(require_admin_user)
):
    try:
        total_tokens = await run_in_threadpool(
            cw_metrics.get_embedding_input_tokens,
            model_id=settings.AWS_BEDROCK_EMBEDDING_MODEL,
            start_time=params.start_time,
            end_time=params.end_time,
        )
    except Exception as e:
        logger.error(
            "embedding_input_token_aggregation_failed",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="embedding input tokens 집계에 실패했습니다."
        )
    
    # TODO: 대상 모델 주입 유연성 확보
    total_costs_usd= round(
        calc_token_cost("cohere.embed-v4", total_tokens), 6
    )
    
    return {"total_costs_usd": total_costs_usd}
