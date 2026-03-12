import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.connectors.github.webhook_ingress import handle_webhook as handle_github_webhook_ingress
from catchup.db.dependencies import get_db
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["github-webhook"])


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    """
    GitHub webhook HTTP entrypoint.
    - signature 검증
    - payload 파싱
    - GitHub webhook ingress 위임
    """
    payload_body = await request.body()

    verify_result = WebhookVerifierProvider.verify_github(
        payload_body=payload_body,
        signature_header=x_hub_signature_256,
        secret=settings.GITHUB_APP_WEBHOOK_SECRET,
    )
    if not verify_result.ok:
        logger.warning(
            "[WEBHOOK][GITHUB][VERIFY] Failed: event=%s, reason=%s",
            x_github_event,
            verify_result.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Webhook Signature",
        )

    try:
        payload = await request.json()
    except Exception:
        logger.warning(
            "[WEBHOOK][GITHUB] Invalid JSON payload: event=%s",
            x_github_event,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    try:
        return await handle_github_webhook_ingress(
            db=db,
            event_name=x_github_event,
            payload=payload,
            schedule_task=background_tasks.add_task,
        )
    except Exception as exc:
        logger.error(
            "[GITHUB][WEBHOOK] Failed to process event: event=%s, error=%s",
            x_github_event,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process GitHub webhook event",
        )
