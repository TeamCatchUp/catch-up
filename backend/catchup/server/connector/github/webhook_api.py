from typing import Optional

import structlog
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.encoders import jsonable_encoder

from catchup.configs.config import settings
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.ingress.github import handle_github_webhook as handle_github_webhook_ingress
from catchup.sync.ingress.types import GithubWebhookRequest

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["github-webhook"])


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
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
            "github_webhook_verify_failed",
            event_name=x_github_event,
            reason=verify_result.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Webhook Signature",
        )

    try:
        payload = await request.json()
    except Exception:
        logger.warning(
            "github_webhook_invalid_json",
            event_name=x_github_event,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    try:
        response = await handle_github_webhook_ingress(
            request=GithubWebhookRequest.from_raw(
                event_name=x_github_event,
                payload=payload,
            ), 
            background_tasks=background_tasks,
        )
        return jsonable_encoder(response, exclude_none=True)
    except Exception as exc:
        logger.error(
            "github_webhook_dispatch_failed",
            event_name=x_github_event,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process GitHub webhook event",
        )
