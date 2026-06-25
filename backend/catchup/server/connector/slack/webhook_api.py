import json
from typing import Optional

import structlog
from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.encoders import jsonable_encoder

from catchup.configs.config import settings
from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.server.connector.slack.schemas import SlackWebhookRequest
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.ingress.slack import handle_slack_webhook as dispatch_slack_webhook

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

    # 1. Webhook Vefiry
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

    # 2. Payload Valid Check
    try:
        payload = await request.json()
        wrapper_type = str(payload.get("type") or "").strip()
    except Exception:
        try:
            form = await request.form()
            raw_payload = form.get("payload")
            if not isinstance(raw_payload, str) or not raw_payload.strip():
                raise ValueError("missing interactivity payload")
            payload = json.loads(raw_payload)
            wrapper_type = str(payload.get("type") or "").strip()
        except Exception:
            logger.warning("slack_webhook_invalid_payload")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Slack payload",
            )

    # 3. Dipatch Slack Webhook Event (Incremental / Metadata / Chat)
    try:
        if wrapper_type == "event_callback" or wrapper_type == "url_verification":
            event_wrapper = SlackEventWrapper(**payload)
            webhook_request = SlackWebhookRequest.from_raw(
                wrapper_type=event_wrapper.type,
                team_id=event_wrapper.team_id or "",
                event=event_wrapper.event,
                challenge=event_wrapper.challenge,
            )
        else:
            webhook_request = SlackWebhookRequest.from_raw(
                wrapper_type=wrapper_type,
                team_id=str((payload.get("team") or {}).get("id") or ""),
                event=payload,
                challenge=None,
            )
        response = await dispatch_slack_webhook(
            request=webhook_request,
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
