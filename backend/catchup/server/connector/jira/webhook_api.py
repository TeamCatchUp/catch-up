from typing import Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from fastapi.encoders import jsonable_encoder
import structlog

from catchup.configs.config import settings
from catchup.connectors.jira.dynamic_webhook_service import JiraDynamicWebhookService
from catchup.connectors.jira.dynamic_webhook_service import get_jira_dynamic_webhook_service
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.ingress.jira import handle_jira_webhook as handle_jira_webhook_ingress
from catchup.sync.ingress.types import JiraWebhookRequest

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/jira", tags=["jira-webhook"])

@router.post("/webhooks/{cloud_id}", status_code=status.HTTP_200_OK)
async def handle_jira_webhook(
    cloud_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Jira Webhook 수신
    - JWT 발신자 검증
    - Project/Sprint/User 이벤트는 즉시 DB 반영
    """
    verify_result = WebhookVerifierProvider.verify_jira(
        authorization=authorization,
        client_secret=settings.ATLASSIAN_CLIENT_SECRET,
        jwt_leeway_seconds=settings.JIRA_WEBHOOK_JWT_LEEWAY_SECONDS,
    )
    if not verify_result.ok:
        logger.warning(
            "jira_webhook_verify_failed",
            cloud_id=cloud_id,
            reason=verify_result.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Jira Webhook Sender",
        )

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning(
            "jira_webhook_invalid_json",
            cloud_id=cloud_id,
            error_type=exc.__class__.__name__,
        )
        payload = {}

    if not isinstance(payload, dict):
        logger.warning(
            "jira_webhook_invalid_payload_type",
            cloud_id=cloud_id,
            payload_type=type(payload).__name__,
        )
        payload = {}

    try:
        response = await handle_jira_webhook_ingress(
            request=JiraWebhookRequest.from_raw(
                cloud_id=cloud_id,
                payload=payload,
            ),
        )
        return jsonable_encoder(response, exclude_none=True)
    except Exception as exc:
        event_type = str(payload.get("webhookEvent") or "").strip()
        logger.error(
            "jira_webhook_dispatch_failed",
            cloud_id=cloud_id,
            event_type=event_type,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process Jira webhook event",
        )


@router.post("/webhooks/{cloud_id}/dynamic/register", status_code=status.HTTP_200_OK)
async def register_dynamic_webhook(
    cloud_id: str,
    project_keys: list[str] | None = Query(
        default=None,
        description="특정 프로젝트만 필터링해서 등록할 때 사용",
    ),
    dynamic_webhook_service: JiraDynamicWebhookService = Depends(get_jira_dynamic_webhook_service),
):
    """
    Jira Dynamic Webhook 등록 강제 실행
    """
    return await dynamic_webhook_service.register_webhook(
        cloud_id=cloud_id,
        source="manual",
        project_keys=project_keys,
    )


@router.post("/webhooks/{cloud_id}/dynamic/refresh", status_code=status.HTTP_200_OK)
async def refresh_dynamic_webhook(
    cloud_id: str,
    force: bool = Query(default=False, description="true면 만료 임박 여부와 무관하게 전체 refresh"),
    dynamic_webhook_service: JiraDynamicWebhookService = Depends(get_jira_dynamic_webhook_service),
):
    """
    Jira Dynamic Webhook 만료 갱신 강제 실행
    """
    return await dynamic_webhook_service.refresh_webhooks(
        cloud_id=cloud_id,
        force=force,
    )


@router.get("/webhooks/{cloud_id}/dynamic/state", status_code=status.HTTP_200_OK)
async def get_dynamic_webhook_state(
    cloud_id: str,
    dynamic_webhook_service: JiraDynamicWebhookService = Depends(get_jira_dynamic_webhook_service),
):
    """
    DB에 저장된 Dynamic Webhook 상태 조회
    """
    subscriptions = await dynamic_webhook_service.sync_webhook_state(cloud_id)

    return {
        "cloud_id": cloud_id,
        "count": len(subscriptions),
        "webhooks": subscriptions,
    }
