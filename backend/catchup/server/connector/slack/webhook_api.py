import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from catchup.configs.config import settings
from catchup.connectors.slack.webhook import handle_webhook as handle_slack_webhook_ingress
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/slack", tags=["slack-webhook"])


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_slack_webhook(
    request: Request,
    x_slack_signature: Optional[str] = Header(None),
    x_slack_request_timestamp: Optional[str] = Header(None),
):
    """
    Slack Event Subscription Webhook 수신 엔드포인트
    """
    payload_body = await request.body()

    verify_result = WebhookVerifierProvider.verify_slack(
        payload_body=payload_body,
        signature=x_slack_signature,
        timestamp=x_slack_request_timestamp,
        signing_secret=settings.SLACK_SIGNING_SECRET,
        tolerance_seconds=300,
    )
    if not verify_result.ok:
        logger.warning(
            "[SLACK][WEBHOOK][VERIFY] Failed: reason=%s",
            verify_result.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack Webhook Signature",
        )

    payload = await request.json()
    try:
        return await run_in_threadpool(
            handle_slack_webhook_ingress,
            payload=payload,
        )
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK] Failed to process event: error=%s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process Slack webhook event",
        )
