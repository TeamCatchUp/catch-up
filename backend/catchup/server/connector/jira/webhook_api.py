import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.connectors.jira.dynamic_webhook_service import (
    JiraDynamicWebhookService,
    get_jira_dynamic_webhook_service,
)
from catchup.connectors.jira import webhook_service
from catchup.db.dependencies import get_db
from catchup.db.jira import webhook_repository as jira_webhook
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.incremental import ingest_record_changes, normalize_jira_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jira", tags=["jira-webhook"])

@router.post("/webhooks/{cloud_id}", status_code=status.HTTP_200_OK)
async def handle_jira_webhook(
    cloud_id: str,
    request: Request,
    db: Session = Depends(get_db),
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
            f"[JIRA][WEBHOOK] Webhook verify failed: cloud_id={cloud_id}, reason={verify_result.reason}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Jira Webhook Sender",
        )
    
    try:
        payload = await request.json()
    except Exception:
        logger.warning(f"[JIRA][WEBHOOK] Invalid JSON payload: cloud_id={cloud_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )
    
    event_type = payload.get("webhookEvent", "")
    
    if event_type in webhook_service.SUPPORTED_METADATA_EVENTS:
        try:
            result = webhook_service.handle_metadata_event(
                db=db,
                cloud_id=cloud_id,
                event_type=event_type,
                payload=payload
            )
            return result
        except Exception as e:
            logger.error(
                f"[JIRA][WEBHOOK] Failed: cloud_id={cloud_id}, event_type={event_type}, error={e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process Jira metadata webhook event",
            )
    
    changes = normalize_jira_event(
        cloud_id=cloud_id,
        payload=payload,
    )
    if not changes:
        logger.info(
            f"[JIRA][WEBHOOK] Ignored unsupported webhook payload: cloud_id={cloud_id}, event_type={event_type}"
        )
        return {"status": "ignored", "event_type": event_type}

    record_keys = ingest_record_changes(db, changes)
    return {
        "status": "accepted",
        "event_type": event_type,
        "record_keys": record_keys,
    }


@router.post("/webhooks/{cloud_id}/dynamic/register", status_code=status.HTTP_200_OK)
async def register_dynamic_webhook(
    cloud_id: str,
    project_keys: list[str] | None = Query(
        default=None,
        description="특정 프로젝트만 필터링해서 등록할 때 사용",
    ),
    db: Session = Depends(get_db),
    dynamic_webhook_service: JiraDynamicWebhookService = Depends(get_jira_dynamic_webhook_service),
):
    """
    Jira Dynamic Webhook 등록 강제 실행
    """
    return await dynamic_webhook_service.register_webhook(
        db=db,
        cloud_id=cloud_id,
        project_keys=project_keys,
    )


@router.post("/webhooks/{cloud_id}/dynamic/refresh", status_code=status.HTTP_200_OK)
async def refresh_dynamic_webhook(
    cloud_id: str,
    force: bool = Query(default=False, description="true면 만료 임박 여부와 무관하게 전체 refresh"),
    db: Session = Depends(get_db),
    dynamic_webhook_service: JiraDynamicWebhookService = Depends(get_jira_dynamic_webhook_service),
):
    """
    Jira Dynamic Webhook 만료 갱신 강제 실행
    """
    return await dynamic_webhook_service.refresh_webhooks(
        db=db,
        cloud_id=cloud_id,
        force=force,
    )


@router.get("/webhooks/{cloud_id}/dynamic/state", status_code=status.HTTP_200_OK)
async def get_dynamic_webhook_state(
    cloud_id: str,
    db: Session = Depends(get_db),
    dynamic_webhook_service: JiraDynamicWebhookService = Depends(get_jira_dynamic_webhook_service),
):
    """
    DB에 저장된 Dynamic Webhook 상태 조회
    """
    await dynamic_webhook_service.sync_webhook_state(db, cloud_id)
    subscriptions = jira_webhook.get_webhooks_by_cloud_id(db, cloud_id)

    return {
        "cloud_id": cloud_id,
        "count": len(subscriptions),
        "webhooks": [
            {
                "webhook_id": subscription.webhook_id,
                "callback_url": subscription.callback_url,
                "jql_filter": subscription.jql_filter,
                "events": jira_webhook.get_webhook_events(subscription),
                "expires_at": (
                    subscription.expires_at.isoformat()
                    if subscription.expires_at else None
                ),
                "last_synced_at": (
                    subscription.last_synced_at.isoformat()
                    if subscription.last_synced_at else None
                ),
            }
            for subscription in subscriptions
        ],
    }
