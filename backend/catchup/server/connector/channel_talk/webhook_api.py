from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from pydantic import Field

from catchup.agents.triggers.resolver import AgentTriggerIngressResult
from catchup.agents.triggers.resolver import handle_verified_webhook_event
from catchup.connector_core.domain.webhooks import VerifiedConnectorWebhookEvent
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.incremental.resolve import resolve_channel_talk_user_chat_event
from catchup.sync.incremental.resolve.channel_talk import ChannelTalkResolveResult
from catchup.sync.incremental.service import get_incremental_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/channel_talk", tags=["channel_talk-webhook"])


class ChannelTalkWebhookResponse(BaseModel):
    status: str
    reason: str | None = None
    record_keys: list[str] = Field(default_factory=list)
    blocked_count: int = 0
    agent_run_ids: list[int] = Field(default_factory=list)


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

    payload = await _read_webhook_payload(request)
    if payload is None:
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

    connection = await _require_verified_connection(
        token=token,
        channel_id=normalized_channel_id,
    )

    # TODO : Incremental Sync & Agent Trigger 모두 VerifiedConnectorWebhookEvent을 받도록 수정
    verified_event = VerifiedConnectorWebhookEvent(
        source="channel_talk",
        event_type=str(payload.get("type") or ""),
        payload=payload,
    )

    sync_dispatch, agent_dispatch = await asyncio.gather(
        run_in_threadpool(
            resolve_channel_talk_user_chat_event,
            trusted_channel_id=connection.channel_id,
            payload=payload,
        ),
        _dispatch_agent_trigger(
            verified_event=verified_event,
            channel_id=connection.channel_id,
        ),
        return_exceptions=True,
    )

    sync_error: Exception | None = None
    if isinstance(sync_dispatch, Exception):
        logger.error(
            "channel_talk_incremental_resolve_failed",
            channel_id=connection.channel_id,
            error=str(sync_dispatch),
        )
        resolved = ChannelTalkResolveResult(
            changes=[],
            reason="incremental_resolve_failed",
        )
        sync_error = sync_dispatch
    else:
        resolved = sync_dispatch

    if isinstance(agent_dispatch, Exception):
        agent_result = AgentTriggerIngressResult(
            status="ignored",
            reason="agent_trigger_dispatch_failed",
        )
        agent_error = agent_dispatch
    else:
        agent_result, agent_error = agent_dispatch

    if sync_error is not None or agent_error is not None:
        errors = []
        if sync_error is not None:
            errors.append(sync_error)
        if agent_error is not None:
            errors.append(agent_error)
        if len(errors) > 1:
            raise HTTPException(
                status_code=500,
                detail="Incremental sync resolve and agent trigger dispatch failed",
            ) from ExceptionGroup(
                "channel_talk_webhook_dispatch_failed",
                errors,
            )
        if sync_error is not None:
            raise HTTPException(
                status_code=500,
                detail="Incremental sync resolve failed",
            ) from sync_error
        raise HTTPException(
            status_code=500,
            detail="Agent trigger dispatch failed",
        ) from agent_error

    if not resolved.changes:
        if agent_result.status == "accepted":
            return ChannelTalkWebhookResponse(
                status="accepted",
                reason=agent_result.reason,
                agent_run_ids=agent_result.run_ids or [],
            )
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
        agent_run_ids=agent_result.run_ids or [],
    )


async def _dispatch_agent_trigger(
    *,
    verified_event: VerifiedConnectorWebhookEvent,
    channel_id: str,
) -> tuple[AgentTriggerIngressResult, Exception | None]:
    try:
        result = await run_in_threadpool(
            handle_verified_webhook_event,
            verified_event,
        )
        return result, None
    except Exception as exc:
        logger.exception(
            "channel_talk_agent_trigger_dispatch_thread_failed",
            channel_id=channel_id,
            error=str(exc),
        )
        return (
            AgentTriggerIngressResult(
                status="ignored",
                reason="agent_trigger_dispatch_failed",
            ),
            exc,
        )


async def _read_webhook_payload(request: Request) -> dict[str, object] | None:
    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning(
            "channel_talk_webhook_invalid_json",
            error=str(exc),
        )
        return None
    if not isinstance(payload, dict):
        return None
    return payload


async def _require_verified_connection(
    *,
    token: str | None,
    channel_id: str,
) -> ChannelTalkCredentialsRecord:
    """Channel Talk token 검증과 trusted channel 확인"""
    connection = await run_in_threadpool(
        load_channel_talk_connection,
        channel_id,
    )
    if connection is None:
        logger.warning(
            "channel_talk_webhook_verify_failed",
            channel_id=channel_id,
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
    return connection


def _extract_channel_id(payload: dict[str, object]) -> str:
    entity = payload.get("entity")
    if not isinstance(entity, dict):
        return ""
    return str(entity.get("channelId") or entity.get("channel_id") or "").strip()
