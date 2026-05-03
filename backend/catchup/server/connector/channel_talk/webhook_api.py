from __future__ import annotations

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from pydantic import Field

from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.incremental.resolve import resolve_channel_talk_user_chat_event
from catchup.sync.incremental.service import get_incremental_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/channel_talk", tags=["channel-talk-webhook"])


class ChannelTalkWebhookResponse(BaseModel):
    status: str
    reason: str | None = None
    record_keys: list[str] = Field(default_factory=list)
    blocked_count: int = 0


@router.post(
    "/webhooks",
    response_model=ChannelTalkWebhookResponse,
)
async def handle_channel_talk_webhook(
    request: Request,
    token: str | None = Query(default=None),
) -> ChannelTalkWebhookResponse:
    if not str(token or "").strip():
        raise HTTPException(status_code=401, detail="Invalid Channel Talk webhook token")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning(
            "channel_talk_webhook_invalid_json",
            error=str(exc),
        )
        return ChannelTalkWebhookResponse(
            status="ignored",
            reason="malformed_body",
        )

    if not isinstance(payload, dict):
        return ChannelTalkWebhookResponse(
            status="ignored",
            reason="malformed_body",
        )

    normalized_channel_id = _extract_channel_id(payload)
    if not normalized_channel_id:
        return ChannelTalkWebhookResponse(
            status="ignored",
            reason="missing_channel_id",
        )

    connection = await run_in_threadpool(
        load_channel_talk_connection,
        normalized_channel_id,
    )
    if connection is None:
        logger.warning(
            "channel_talk_webhook_verify_failed",
            channel_id=normalized_channel_id,
            reason="unknown_channel",
        )
        raise HTTPException(status_code=401, detail="Invalid Channel Talk webhook token")

    verify_result = WebhookVerifierProvider.verify_channel_talk(
        token=token,
        expected_token=connection.webhook_token,
    )
    if not verify_result.ok:
        logger.warning(
            "channel_talk_webhook_verify_failed",
            channel_id=connection.channel_id,
            reason=verify_result.reason,
        )
        raise HTTPException(status_code=401, detail="Invalid Channel Talk webhook token")

    resolved = resolve_channel_talk_user_chat_event(
        trusted_channel_id=connection.channel_id,
        payload=payload,
    )
    if not resolved.changes:
        return ChannelTalkWebhookResponse(
            status="ignored",
            reason=resolved.reason or "unsupported_event",
        )

    result = await get_incremental_service().dispatch_changes(
        changes=resolved.changes,
    )
    return ChannelTalkWebhookResponse(
        status="accepted",
        record_keys=result.record_keys,
        blocked_count=result.blocked_count,
    )


def _extract_channel_id(payload: dict[str, object]) -> str:
    entity = payload.get("entity")
    if not isinstance(entity, dict):
        return ""
    return str(entity.get("channelId") or entity.get("channel_id") or "").strip()
