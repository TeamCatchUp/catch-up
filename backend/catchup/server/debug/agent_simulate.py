"""Execution Agent 디버그용 엔드포인트.

실제 웹훅 엔드포인트는 각 커넥터 담당자가 구현한다.
이 라우터는 Swagger에서 웹훅 수신을 시뮬레이션하기 위한 용도로만 사용한다.
"""
import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import Field
from sqlalchemy.orm import Session

from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.resolver import handle_agent_webhook_event
from catchup.db.dependencies import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


class WebhookSimulateResponse(AgentWebhookEvent):
    status: str
    reason: str | None = None
    run_ids: list[int] = Field(default_factory=list)
    matched_count: int = 0
    result: str | None
    matched: bool


@router.post(
    "/simulate-webhook",
    response_model=WebhookSimulateResponse,
    status_code=status.HTTP_200_OK,
    summary="웹훅 수신 시뮬레이션 (디버그용)",
    description=(
        "정규화된 AgentWebhookEvent를 지정해 trigger resolver → run/outbox 저장 흐름을 테스트한다. "
        "agent_triggers에 매칭되는 트리거가 없으면 matched=false를 반환한다."
    ),
)
async def simulate_webhook(
    body: AgentWebhookEvent,
    db: Session = Depends(get_db),
) -> WebhookSimulateResponse:
    try:
        ingress = handle_agent_webhook_event(
            db=db,
            event=body,
        )
    except Exception as e:
        logger.exception(
            "simulate_webhook_error",
            event_id=body.event_id,
            source=body.source,
            event_type=body.event_type,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    run_ids = ingress.run_ids or []
    return WebhookSimulateResponse(
        **body.model_dump(),
        status=ingress.status,
        reason=ingress.reason,
        run_ids=run_ids,
        matched_count=ingress.matched_count,
        result=",".join(str(run_id) for run_id in run_ids) if run_ids else None,
        matched=ingress.status == "accepted",
    )
