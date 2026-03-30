from typing import Optional

from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.encoders import jsonable_encoder
import structlog

from catchup.configs.config import settings
from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.ingress.slack import handle_slack_webhook as handle_slack_webhook_ingress
from catchup.sync.ingress.types import SlackWebhookRequest

logger = structlog.get_logger(__name__)

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
            "slack_webhook_verify_failed",
            reason=verify_result.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack Webhook Signature",
        )

    try:
        payload = await request.json()
    except Exception:
        logger.warning("slack_webhook_invalid_json")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    try:
        event_wrapper = SlackEventWrapper(**payload)
        response = await handle_slack_webhook_ingress(
            request=SlackWebhookRequest.from_raw(
                wrapper_type=event_wrapper.type,
                team_id=event_wrapper.team_id or "",
                event=event_wrapper.event,
                challenge=event_wrapper.challenge,
            ),
        )
        return jsonable_encoder(response, exclude_none=True)
    except Exception as exc:
        logger.error(
            "slack_webhook_dispatch_failed",
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process Slack webhook event",
        )
