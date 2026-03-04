import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.connectors.slack import webhook_service
from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.db.dependencies import get_db
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/slack", tags=["slack-webhook"])


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_slack_webhook(
    request: Request,
    db: Session = Depends(get_db),
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
    event_wrapper = SlackEventWrapper(**payload)

    if event_wrapper.type == "url_verification":
        logger.info("[SLACK][WEBHOOK] URL verification received")
        return {"challenge": event_wrapper.challenge}

    if event_wrapper.type != "event_callback":
        logger.warning(
            "[SLACK][WEBHOOK] Unknown wrapper type: type=%s",
            event_wrapper.type,
        )
        return {"status": "ignored", "wrapper_type": event_wrapper.type}

    if not event_wrapper.event:
        logger.warning("[SLACK][WEBHOOK] Empty event callback")
        return {"status": "ignored", "reason": "empty_event"}

    if not event_wrapper.team_id:
        logger.warning("[SLACK][WEBHOOK] Missing team_id in callback")
        return {"status": "ignored", "reason": "missing_team_id"}

    event = event_wrapper.event
    event_type = event.get("type")
    event_subtype = event.get("subtype")
    team_id = event_wrapper.team_id

    logger.info(
        "[SLACK][WEBHOOK] Received event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )

    if event_type == "message" and event_subtype in (None, "bot_message"):
        return await _handle_message_event(team_id, event)

    if event_type in ["channel_created", "channel_rename", "group_created", "group_rename"]:
        return _handle_channel_upsert_event(team_id, event, db)

    if event_type in ["channel_deleted", "group_deleted"]:
        return _handle_channel_deleted_event(team_id, event, db)

    if event_type in ["channel_archive", "channel_unarchive", "group_archive", "group_unarchive"]:
        return _handle_channel_archive_event(team_id, event, db)

    if event_type in ["member_joined_channel", "member_left_channel"]:
        return _handle_member_event(team_id, event, db)

    if event_type in ["team_join", "user_change"]:
        return _handle_user_event(team_id, event, db)

    logger.debug(
        "[SLACK][WEBHOOK] Ignored unsupported event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )
    return {"status": "ignored", "event_type": event_type}

async def _handle_message_event(team_id: str, event: dict) -> dict:
    """
    Redis 기반 버퍼 경로 폐기 후 메시지 이벤트를 무시
    """
    logger.warning(
        "[SLACK][INCREMENTAL SYNC][WEBHOOK] Message buffering disabled: team_id=%s, channel_id=%s, ts=%s",
        team_id,
        event.get("channel"),
        event.get("ts"),
    )
    return {"status": "ignored", "reason": "incremental_pipeline_disabled"}


def _handle_channel_upsert_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 생성/이름변경 이벤트 처리"""
    try:
        webhook_service.handle_channel_upsert(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK] Channel upsert failed: team_id=%s, error=%s",
            team_id,
            exc,
        )
        return {"status": "error", "reason": "processing_failed"}


def _handle_channel_deleted_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 삭제 이벤트 처리"""
    try:
        webhook_service.handle_channel_delete(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK] Channel delete failed: team_id=%s, error=%s",
            team_id,
            exc,
        )
        return {"status": "error", "reason": "processing_failed"}


def _handle_channel_archive_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 아카이브/해제 이벤트 처리"""
    try:
        webhook_service.handle_channel_archive(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK] Channel archive failed: team_id=%s, error=%s",
            team_id,
            exc,
        )
        return {"status": "error", "reason": "processing_failed"}


def _handle_member_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 멤버십 변경 이벤트 처리"""
    try:
        webhook_service.handle_member_event(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK] Member event failed: team_id=%s, error=%s",
            team_id,
            exc,
        )
        return {"status": "error", "reason": "processing_failed"}


def _handle_user_event(team_id: str, event: dict, db: Session) -> dict:
    """사용자 변경 이벤트 처리"""
    try:
        webhook_service.handle_user_event(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as exc:
        logger.error(
            "[SLACK][WEBHOOK] User event failed: team_id=%s, error=%s",
            team_id,
            exc,
        )
        return {"status": "error", "reason": "processing_failed"}
