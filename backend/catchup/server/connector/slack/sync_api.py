import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.connectors.slack.schemas import SlackEventWrapper, SlackMessageEvent
from catchup.connectors.slack import webhook_service
from catchup.configs.config import settings
from catchup.server.connector.slack.schemas import (
    ChannelAccessInfo,
    ChannelAccessResponse,
    SlackFlushResponse,
    SlackFlushTeamResult,
    SlackSyncResponse,
    SlackSyncStatusResponse,
    SyncResultDetail,
)
from catchup.db.dependencies import get_db
from catchup.db.models import SlackSyncState
from catchup.db.slack.oauth_repository import get_all_slack_tokens
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.utils.webhook_buffer import get_webhook_buffer

logger = logging.getLogger(__name__)


# ================================================================
# Router
# ================================================================

router = APIRouter(prefix="/api/v1/slack/sync", tags=["slack-sync"])


@router.post("/full", response_model=SlackSyncResponse)
async def trigger_full_sync(
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    sync_days: int | None = Query(None, description="수집 범위 (일), 기본값 3년"),
    db: Session = Depends(get_db),
):
    """
    전체 동기화 트리거

    지정된 채널(또는 전체)의 모든 Slack 데이터를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    try:
        service = await create_slack_ingestion_service(db, team_id)
        result = await service.full_sync(db, sync_days=sync_days)

        messages = result.get("messages", {})
        synced = messages.get("synced", 0)
        skipped = messages.get("skipped", 0)

        message = f"Slack Full Sync 완료 : {synced}개 저장"
        if skipped > 0:
            message += f" {skipped}개 채널 권한 없음"
        
        return SlackSyncResponse(
            status="success",
            message=message,
            team_id=team_id,
            results={
                "messages": SyncResultDetail(
                    synced=messages.get("synced", 0),
                    errors=messages.get("errors", 0),
                    skipped=messages.get("skipped", 0),
                )
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SLACK][FULL SYNC] Slack Full Sync Failed for team_id = {team_id} : {e}")
        raise HTTPException(
            status_code = 500,
            detail = f"동기화 과정 중 오류 발생 : {str(e)}",
        )


@router.post("/flush", response_model=SlackFlushResponse)
async def flush_all_slack_buffers(
    db: Session = Depends(get_db),
):
    """
    모든 Slack Workspace의 Redis 버퍼를 즉시 flush하고 증분 동기화

    스케줄러가 정각에 자동으로 실행하는 작업을 수동으로 트리거합니다.
    모든 연결된 Slack Workspace를 순회하며:
    1. Redis에서 버퍼링된 이벤트가 있는 채널 조회
    2. 각 채널별로 버퍼 클리어 및 이벤트 개수 카운트
    3. Incremental Sync 실행
    4. 팀별 결과 수집 및 전체 통계 반환
    """
    logger.info("Starting manual Slack webhook flush for all teams")

    buffer = get_webhook_buffer()
    results = []
    total_events = 0
    total_synced = 0
    flushed_teams_count = 0

    try:
        # 모든 Slack Token 조회
        tokens = get_all_slack_tokens(db)

        if not tokens:
            logger.info("No Slack tokens found")
            return SlackFlushResponse(
                status="success",
                message="연결된 Slack Workspace가 없습니다",
                total_teams=0,
                flushed_teams=0,
                total_events=0,
                total_synced=0,
            )

        logger.info(f"Found {len(tokens)} Slack workspaces to process")

        # 각 팀별로 처리
        for token in tokens:
            team_id = token.team_id
            team_name = token.team_name

            try:
                # 버퍼링된 채널 조회
                channels_with_events = await buffer.get_slack_buffered_channels(team_id)

                if not channels_with_events:
                    logger.debug(f"No buffered events for team {team_id}")
                    results.append(SlackFlushTeamResult(
                        team_id=team_id,
                        team_name=team_name,
                        flushed_channels=0,
                        flushed_events=0,
                        synced_messages=0,
                        status="no_events",
                    ))
                    continue

                logger.info(
                    f"Flushing events for team {team_id}: "
                    f"{len(channels_with_events)} channels affected"
                )

                # 채널별 버퍼 클리어
                team_events = 0
                for channel_id in channels_with_events:
                    try:
                        event_count = await buffer.clear_slack_buffer(team_id, channel_id)
                        team_events += event_count
                        logger.info(
                            f"Cleared {event_count} events for channel {channel_id} "
                            f"(team {team_id})"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to clear buffer for channel {channel_id}: {e}",
                            exc_info=True,
                        )

                try:
                    service = await create_slack_ingestion_service(db, team_id)
                    sync_result = await service.flush_message(db, channels_with_events)

                    team_synced = sum(
                        entity_result.get("synced", 0)
                        for entity_result in sync_result.values()
                    )

                    total_events += team_events
                    total_synced += team_synced
                    flushed_teams_count += 1

                    results.append(SlackFlushTeamResult(
                        team_id=team_id,
                        team_name=team_name,
                        flushed_channels=len(channels_with_events),
                        flushed_events=team_events,
                        synced_messages=team_synced,
                        status="success",
                    ))

                    logger.info(
                        f"Successfully flushed team {team_id}: "
                        f"{team_events} events, {team_synced} messages synced"
                    )

                except Exception as e:
                    logger.error(f"Failed to sync team {team_id}: {e}", exc_info=True)
                    results.append(SlackFlushTeamResult(
                        team_id=team_id,
                        team_name=team_name,
                        flushed_channels=len(channels_with_events),
                        flushed_events=team_events,
                        synced_messages=0,
                        status="error",
                        error_message=str(e),
                    ))

            except Exception as e:
                logger.error(
                    f"Failed to process team {team_id}: {e}",
                    exc_info=True,
                )
                results.append(SlackFlushTeamResult(
                    team_id=team_id,
                    team_name=team_name,
                    flushed_channels=0,
                    flushed_events=0,
                    synced_messages=0,
                    status="error",
                    error_message=str(e),
                ))

        message = (
            f"전체 flush 완료: {len(tokens)}개 팀 중 {flushed_teams_count}개 처리, "
            f"{total_events}개 이벤트, {total_synced}개 메시지 동기화"
        )

        logger.info(f"Slack flush completed: {message}")

        return SlackFlushResponse(
            status="success",
            message=message,
            total_teams=len(tokens),
            flushed_teams=flushed_teams_count,
            total_events=total_events,
            total_synced=total_synced,
            results=results,
        )

    except Exception as e:
        logger.error(f"Flush all error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"전체 flush 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/status", response_model=list[SlackSyncStatusResponse])
async def get_sync_status(
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
):
    """
    동기화 상태 조회

    해당 Slack Workspace의 엔티티별 동기화 상태를 반환.
    """
    stmt = select(SlackSyncState).where(SlackSyncState.team_id == team_id)
    result = db.execute(stmt)
    sync_states = result.scalars().all()

    if not sync_states:
        return []

    return [
        SlackSyncStatusResponse(
            team_id=state.team_id,
            entity_type=state.entity_type,
            last_sync_status=state.last_sync_status,
            last_successful_sync_at=(
                state.last_successful_sync_at.isoformat()
                if state.last_successful_sync_at
                else None
            ),
            synced_entities=state.synced_entities or 0,
            last_sync_error=state.last_sync_error,
            oldest_ts=state.oldest_ts,
            latest_ts=state.latest_ts,
        )
        for state in sync_states
    ]


@router.get("/accessible/channels", response_model=ChannelAccessResponse)
async def debug_channel_access(
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
):
    """
    Bot이 접근 권한이 있는 채널 목록 조회

    각 채널별로:
    - channel_type: public, private, dm, mpim
    - is_member: Bot이 멤버인지 여부
    - is_private: 비공개 채널 여부
    """
    try:
        service = await create_slack_ingestion_service(db, team_id)

        channels = []
        cursor = None

        while True:
            response = await service.client.list_conversations(
                types="public_channel,private_channel,mpim,im",
                cursor=cursor,
            )

            for ch in response.get("channels", []):
                # 채널 타입 결정
                if ch.get("is_im"):
                    channel_type = "dm"
                elif ch.get("is_mpim"):
                    channel_type = "mpim"
                elif ch.get("is_private"):
                    channel_type = "private"
                else:
                    channel_type = "public"

                channels.append(ChannelAccessInfo(
                    id=ch.get("id", ""),
                    name=ch.get("name", ch.get("id", "unknown")),
                    channel_type=channel_type,
                    is_member=ch.get("is_member", False),
                    is_private=ch.get("is_private", False),
                    member_count=ch.get("num_members"),
                ))

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        # is_member=True인 채널 수
        accessible = sum(1 for c in channels if c.is_member)

        return ChannelAccessResponse(
            team_id=team_id,
            total_channels=len(channels),
            accessible_channels=accessible,
            channels=channels,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug channel access error for team_id={team_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"채널 조회 중 오류가 발생했습니다: {str(e)}",
        )


# =============================================================================
# Webhook Endpoints
# =============================================================================

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

    # 0. Signature 검증
    verify_result = WebhookVerifierProvider.verify_slack(
        payload_body=payload_body,
        signature=x_slack_signature,
        timestamp=x_slack_request_timestamp,
        signing_secret=settings.SLACK_SIGNING_SECRET,
        tolerance_seconds=300,
    )
    if not verify_result.ok:
        logger.warning(
            f"[WEBHOOK][SLACK][VERIFY] Failed: reason={verify_result.reason}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack Webhook Signature",
        )

    payload = await request.json()
    event_wrapper = SlackEventWrapper(**payload)

    # 1. URL Verification (최초 설정 시 수신)
    if event_wrapper.type == "url_verification":
        logger.info("[SLACK][EVENT] URL Verification Received")
        return {"challenge": event_wrapper.challenge}

    # 2. Event Callback 처리
    if event_wrapper.type == "event_callback":
        if not event_wrapper.event:
            logger.warning("[SLACK][EVENT] Empty Event Callback Received")
            return {"status": "ignored", "reason": "empty_event"}

        if not event_wrapper.team_id:
            logger.warning("[SLACK][EVENT] Event Callback without team_id")
            return {"status": "ignored", "reason": "missing_team_id"}

        event = event_wrapper.event
        event_type = event.get("type")
        event_subtype = event.get("subtype")
        team_id = event_wrapper.team_id

        logger.info(
            f"[SLACK][EVENT] Received: type={event_type}, subtype={event_subtype}, team_id={team_id}"
        )

        # Message Event → Redis Buffer
        if event_type == "message" and event_subtype is None:
            return await _handle_message_event(team_id, event)

        # Channel Created / Renamed (channel이 object)
        if event_type in [
            "channel_created", "channel_rename",
            "group_created", "group_rename",
        ]:
            return _handle_channel_upsert_event(team_id, event, db)

        # Channel Deleted (channel이 string ID)
        if event_type in ["channel_deleted", "group_deleted"]:
            return _handle_channel_deleted_event(team_id, event, db)

        # Channel Archive / Unarchive (channel이 string ID)
        if event_type in [
            "channel_archive", "channel_unarchive",
            "group_archive", "group_unarchive",
        ]:
            return _handle_channel_archive_event(team_id, event, db)

        # 멤버십 이벤트
        if event_type in ["member_joined_channel", "member_left_channel"]:
            return _handle_member_event(team_id, event, db)

        # 사용자 이벤트
        if event_type in ["team_join", "user_change"]:
            return _handle_user_event(team_id, event, db)
        
        # 처리하지 않는 이벤트
        logger.debug(f"Unhandled Slack event: type={event_type}, subtype={event_subtype}")
        return {"status": "ignored", "event_type": event_type}
    
    # 알 수 없는 타입
    logger.warning(f"Unknown Slack webhook type: {event_wrapper.type}")
    return {"status": "ignored", "wrapper_type": event_wrapper.type}


# =============================================================================
# Private Helper Functions
# =============================================================================

async def _handle_message_event(team_id: str, event: dict) -> dict:
    """
    Message Event를 Redis Buffer에 저장
    """
    try:
        data = SlackMessageEvent(**event)
    except Exception as e:
        logger.error(f"[SLACK][EVENT] Failed to Parse Message Event: {e}")
        return {"status": "error", "reason": "parse_failed"}

    if not data.user:
        logger.debug(f"[SLACK][EVENT] Ignored bot message: channel={data.channel}, ts={data.ts}")
        return {"status": "skipped", "reason": "bot_message"}

    if data.subtype is not None:
        logger.debug(f"[SLACK][EVENT] Ignored message with subtype: channel={data.channel}, ts={data.ts}")
        return {"status": "skipped", "reason": "subtype_message"}

    buffer = get_webhook_buffer()
    await buffer.buffer_slack_event(
        team_id=team_id,
        channel_id=data.channel,
        message_ts=data.ts,
        event_type="message"
    )

    logger.info(
        f"[SLACK][EVENT] Buffered Slack message: team={team_id}, "
        f"channel={data.channel}, ts={data.ts}, user={data.user}"
    )
    return {"status": "buffered", "event_type": "message"}


def _handle_channel_upsert_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 생성/이름변경 → webhook_service 위임"""
    try:
        webhook_service.handle_channel_upsert(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as e:
        logger.error(f"[SLACK][EVENT] Channel upsert failed: {e}")
        return {"status": "error", "reason": "processing_failed"}


def _handle_channel_deleted_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 삭제 → webhook_service 위임"""
    try:
        webhook_service.handle_channel_delete(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as e:
        logger.error(f"[SLACK][EVENT] Channel delete failed: {e}")
        return {"status": "error", "reason": "processing_failed"}


def _handle_channel_archive_event(team_id: str, event: dict, db: Session) -> dict:
    """채널 아카이브/해제 → webhook_service 위임"""
    try:
        webhook_service.handle_channel_archive(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as e:
        logger.error(f"[SLACK][EVENT] Channel archive failed: {e}")
        return {"status": "error", "reason": "processing_failed"}


def _handle_member_event(team_id: str, event: dict, db: Session) -> dict:
    """멤버십 변경 → webhook_service 위임"""
    try:
        webhook_service.handle_member_event(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as e:
        logger.error(f"[SLACK][EVENT] Member event failed: {e}")
        return {"status": "error", "reason": "processing_failed"}


def _handle_user_event(team_id: str, event: dict, db: Session) -> dict:
    """사용자 변경 → webhook_service 위임"""
    try:
        webhook_service.handle_user_event(db, team_id, event)
        return {"status": "processed", "event_type": event.get("type")}
    except Exception as e:
        logger.error(f"[SLACK][EVENT] User event failed: {e}")
        return {"status": "error", "reason": "processing_failed"}
