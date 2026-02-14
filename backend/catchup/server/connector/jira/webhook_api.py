import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status

from catchup.configs.config import settings
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.utils.webhook_buffer import get_webhook_buffer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jira", tags=["jira-webhook"])

SUPPORTED_ISSUE_EVENTS = {
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "comment_created",
    "comment_updated",
    "comment_deleted",
}

def _extract_issue_project(payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Payload에서 Issue Key + Project Key 추출"""
    issue = payload.get("issue") or {}
    issue_key = issue.get("key")

    fields = issue.get("fields") or {}
    project = fields.get("project") or payload.get("project") or {}
    project_key = project.get("key")

    return issue_key, project_key

@router.post("/webhooks/{cloud_id}", status_code=status.HTTP_200_OK)
async def handle_jira_webhook(
    cloud_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Jira Webhook 수신
    - OAuth JWT 발신자 검증
    - Issue/Comment 이벤트를 Redis Buffer에 적재
    """

    verify_result = WebhookVerifierProvider.verify_jira(
        authorization=authorization,
        client_secret=settings.JIRA_CLIENT_SECRET,
    )

    if not verify_result.ok:
        logger.warning(
            f"[JIRA][WEBHOOK] Signature Verify Failed : cloud_id = {cloud_id}, reason = {verify_result.reason}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Jira Webhook Sender"
        )

    try:
        payload = await request.json()
    except Exception:
        logger.warning(f"[JIRA][WEBHOOK] Invalid JSON Payload cloud_id={cloud_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON Payload",
        )

    event_type = payload.get("webhookEvent", "")


    if event_type not in SUPPORTED_ISSUE_EVENTS:
        logger.info(
            f"[JIRA][WEBHOOK] Unsupported Event Type cloud_id={cloud_id}, event={event_type}"
        )
        return {"status": "ignored", "event_type": event_type}

    issue_key, project_key = _extract_issue_project(payload)
    if not issue_key or not project_key:
        logger.info(
            f"[JIRA][WEBHOOK] Ignored Event : cloud_id={cloud_id}, event_type={event_type}, reason=missing_issue_or_project"
        )
        return {"status": "ignored", "event_type": event_type}

    buffer = get_webhook_buffer()
    await buffer.buffer_jira_event(
        cloud_id=cloud_id,
        project_key=project_key,
        issue_key=issue_key,
        event_type=event_type,
    )

    logger.info(
        f"[JIRA][WEBHOOK] Buffered Event cloud_id={cloud_id}, project_key={project_key}, event_type={event_type}"
    )

    return {"status": "buffered", "event_type": event_type}
