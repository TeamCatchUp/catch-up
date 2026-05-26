"""Execution Agent 디버그용 엔드포인트.

실제 웹훅 엔드포인트는 각 커넥터 담당자가 구현한다.
이 라우터는 Swagger에서 웹훅 수신을 시뮬레이션하기 위한 용도로만 사용한다.
"""
import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy.orm import Session

from catchup.agents.triggers.resolver import dispatch_webhook
from catchup.db.dependencies import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


class WebhookSimulateRequest(BaseModel):
    source: str = Field(
        examples=["channel_talk"],
        description="이벤트 소스 (agent_triggers.source와 매칭)",
    )
    payload: dict = Field(
        examples=[{
            "event_type": "new_message",
            "channel_id": "ch-001",
            "user_name": "김철수",
            "message": "결제 오류가 계속 발생합니다. 도와주세요.",
        }],
        description="웹훅 원본 payload. filter_condition KV 매칭에 사용된다.",
    )


class WebhookSimulateResponse(BaseModel):
    result: str | None
    matched: bool


@router.post(
    "/simulate-webhook",
    response_model=WebhookSimulateResponse,
    status_code=status.HTTP_200_OK,
    summary="웹훅 수신 시뮬레이션 (디버그용)",
    description=(
        "source와 payload를 직접 지정해 trigger resolver → Execution Agent 실행 흐름을 테스트한다. "
        "agent_triggers에 매칭되는 트리거가 없으면 matched=false를 반환한다."
    ),
)
async def simulate_webhook(
    body: WebhookSimulateRequest,
    db: Session = Depends(get_db),
) -> WebhookSimulateResponse:
    try:
        result = await dispatch_webhook(
            db=db,
            source=body.source,
            payload=body.payload,
        )
    except Exception as e:
        logger.exception("simulate_webhook_error", source=body.source)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    return WebhookSimulateResponse(
        result=result,
        matched=result is not None,
    )
