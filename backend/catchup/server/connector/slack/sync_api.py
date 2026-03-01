import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.connectors.slack.schemas import SlackEventWrapper, SlackMessageEvent
from catchup.connectors.slack.sync_runtime import events as runtime_events
from catchup.connectors.slack.sync_runtime import job_store
from catchup.connectors.slack.sync_runtime import locks as runtime_locks
from catchup.connectors.slack.sync_runtime import queue as runtime_queue
from catchup.connectors.slack import webhook_service
from catchup.connectors.slack.sync_runtime.audit import (
    emit_job_accepted,
    emit_job_completed,
    emit_job_failed,
    emit_team_lock_conflict,
)
from catchup.connectors.slack.sync_runtime.constants import (
    SyncEventType,
    SyncFailureReason,
    SyncJobStatus,
)
from catchup.connectors.slack.sync_runtime.schemas import (
    SlackChannelSyncTask,
    SyncJobMeta,
)
from catchup.configs.config import settings
from catchup.db.models import User
from catchup.server.connector.slack.schemas import (
    ChannelAccessInfo,
    ChannelAccessResponse,
    SlackFullSyncAcceptedResponse,
    SlackFullSyncRequest,
    SlackIncrementalAcceptedResponse,
    SlackIncrementalFlushRequest,
    SlackIncrementalNoEventsResponse,
    SlackSyncStatusResponse,
)
from catchup.db.dependencies import get_db
from catchup.db.models import SlackEntityType, SlackSyncState
from catchup.db.slack import sync_repository as slack_sync
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.utils.webhook_buffer import get_webhook_buffer

logger = logging.getLogger(__name__)


# ================================================================
# Router
# ================================================================

router = APIRouter(prefix="/api/v1/slack/sync", tags=["slack-sync"])


def _build_job_urls(base_url: str | None, job_id: str) -> tuple[str | None, str | None]:
    if not base_url:
        return None, None
    base = base_url.rstrip("/")
    return (
        f"{base}/api/v1/sync/jobs/{job_id}",
        f"{base}/api/v1/sync/jobs/{job_id}/stream",
    )


def _resolve_team_incremental_sync_from(db: Session, team_id: str) -> str:
    sync_state = slack_sync.get_sync_state(db, team_id, SlackEntityType.MESSAGE)
    if sync_state and sync_state.last_successful_sync_at:
        return str(sync_state.last_successful_sync_at.timestamp())

    fallback_hours = max(1, settings.SYNC_INCREMENTAL_FALLBACK_HOURS)
    fallback_from = datetime.now(timezone.utc) - timedelta(hours=fallback_hours)
    return str(fallback_from.timestamp())


async def enqueue_incremental_sync_job(
    *,
    db: Session,
    team_id: str,
    base_url: str | None = None,
    trigger: str = "api",
) -> dict:
    buffer = get_webhook_buffer()
    job_id = uuid4().hex
    enqueued_at = datetime.now(timezone.utc).isoformat()

    lock_acquired = False
    job_created = False
    tasks_enqueued = False
    dropped_channels = 0
    dropped_events = 0

    try:
        lock_acquired, owner_job_id = await runtime_locks.acquire_team_lock(team_id, job_id)
        if not lock_acquired:
            emit_team_lock_conflict(
                team_id=team_id,
                requested_job_id=job_id,
                owner_job_id=owner_job_id,
                sync_type="incremental",
            )
            return {
                "status": "conflict",
                "team_id": team_id,
                "owner_job_id": owner_job_id,
                "message": "incremental sync already in progress for this team",
            }

        channels_with_events = await buffer.get_slack_buffered_channels(team_id)
        if not channels_with_events:
            await runtime_locks.release_team_lock_if_owner(team_id, job_id)
            lock_acquired = False
            return {
                "status": "no_events",
                "team_id": team_id,
                "dropped_channels": 0,
                "dropped_events": 0,
                "message": "no buffered events for this team",
            }

        team_sync_from = _resolve_team_incremental_sync_from(db, team_id)
        tasks: list[SlackChannelSyncTask] = []
        for channel_id in channels_with_events:
            channel_state = slack_sync.get_channel_sync_state(db, team_id, channel_id)
            if channel_state is None:
                dropped_channels += 1
                try:
                    dropped_events += await buffer.clear_slack_buffer(team_id, channel_id)
                except Exception:
                    logger.exception(
                        "[SLACK][INCREMENTAL SYNC][API] Failed to clear stale buffered channel: team_id=%s, channel_id=%s",
                        team_id,
                        channel_id,
                    )
                continue

            channel_sync_from = channel_state.latest_synced_ts or team_sync_from
            channel_name = channel_state.channel_name or channel_id
            tasks.append(
                SlackChannelSyncTask(
                    sync_type="incremental",
                    event_id=uuid4().hex,
                    job_id=job_id,
                    team_id=team_id,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    sync_from=channel_sync_from,
                    attempt=0,
                    max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
                    enqueued_at=enqueued_at,
                )
            )

        if not tasks:
            await runtime_locks.release_team_lock_if_owner(team_id, job_id)
            lock_acquired = False
            return {
                "status": "no_events",
                "team_id": team_id,
                "dropped_channels": dropped_channels,
                "dropped_events": dropped_events,
                "message": "no syncable buffered channels for this team",
            }

        total_channels = len(tasks)
        job_meta = SyncJobMeta(
            job_id=job_id,
            team_id=team_id,
            sync_type="incremental",
            created_at=enqueued_at,
            total_channels=total_channels,
            queued_channels=total_channels,
            dropped_channels=dropped_channels,
            dropped_events=dropped_events,
        )
        await job_store.create_job(job_meta)
        job_created = True

        await runtime_events.append_event(
            job_id=job_id,
            team_id=team_id,
            event_type=SyncEventType.JOB_CREATED,
            payload={
                "sync_type": "incremental",
                "trigger": trigger,
                "total_channels": total_channels,
                "queued_channels": total_channels,
                "dropped_channels": dropped_channels,
                "dropped_events": dropped_events,
            },
        )
        emit_job_accepted(
            job_id=job_id,
            team_id=team_id,
            total_channels=total_channels,
            queued_channels=total_channels,
            sync_type="incremental",
            dropped_channels=dropped_channels,
            dropped_events=dropped_events,
            trigger=trigger,
        )

        await runtime_queue.enqueue_tasks(tasks)
        tasks_enqueued = True

        snapshot_url, stream_url = _build_job_urls(base_url, job_id)
        return {
            "status": "accepted",
            "job_id": job_id,
            "team_id": team_id,
            "total_channels": total_channels,
            "queued_channels": total_channels,
            "dropped_channels": dropped_channels,
            "dropped_events": dropped_events,
            "snapshot_url": snapshot_url,
            "stream_url": stream_url,
        }
    except Exception as e:
        logger.error(
            "[SLACK][INCREMENTAL SYNC][API] Failed to enqueue incremental sync: team_id=%s, error=%s",
            team_id,
            e,
            exc_info=True,
        )

        if job_created and not tasks_enqueued:
            await job_store.update_job_fields(
                job_id,
                {
                    "status": SyncJobStatus.FAILED.value,
                    "started_at": enqueued_at,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": str(e),
                },
            )
            await runtime_events.append_event(
                job_id=job_id,
                team_id=team_id,
                event_type=SyncEventType.JOB_FAILED,
                payload={"error": str(e)},
            )
            emit_job_failed(
                job_id=job_id,
                team_id=team_id,
                failure_reason=SyncFailureReason.UNEXPECTED_ERROR.value,
                error_summary=str(e),
                sync_type="incremental",
            )

        if lock_acquired and not tasks_enqueued:
            await runtime_locks.release_team_lock_if_owner(team_id, job_id)

        return {
            "status": "error",
            "team_id": team_id,
            "message": str(e),
        }


@router.post(
    "/full",
    response_model=SlackFullSyncAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_full_sync(
    full_sync_request: SlackFullSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    """
    전체 동기화 트리거

    지정된 채널(또는 전체)의 모든 Slack 데이터를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    team_id = full_sync_request.team_id
    requested_channel_ids = full_sync_request.channel_ids
    sync_days = full_sync_request.sync_days

    days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
    sync_from = str((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    enqueued_at = datetime.now(timezone.utc).isoformat()
    job_id = uuid4().hex

    lock_acquired = False
    job_created = False
    tasks_enqueued = False
    try:
        lock_acquired, owner_job_id = await runtime_locks.acquire_team_lock(team_id, job_id)
        if not lock_acquired:
            emit_team_lock_conflict(
                team_id=team_id,
                requested_job_id=job_id,
                owner_job_id=owner_job_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "team_id": team_id,
                    "owner_job_id": owner_job_id,
                    "message": "full sync already in progress for this team",
                },
            )

        service = await create_slack_ingestion_service(db, team_id)
        channels = await service.list_syncable_channels()
        normalized_requested_channel_ids: list[str] | None = None
        invalid_channel_ids: list[str] = []
        if requested_channel_ids is not None:
            deduplicated_ids = dict.fromkeys(
                channel_id.strip()
                for channel_id in requested_channel_ids
                if channel_id and channel_id.strip()
            )
            normalized_requested_channel_ids = list(deduplicated_ids.keys())
            if not normalized_requested_channel_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "team_id": team_id,
                        "message": "channel_ids must include at least one non-empty channel id",
                    },
                )

            channel_by_id: dict[str, dict[str, str]] = {}
            for channel in channels:
                channel_id = channel.get("id")
                if channel_id:
                    channel_by_id[channel_id] = channel

            filtered_channels: list[dict[str, str]] = []
            for channel_id in normalized_requested_channel_ids:
                channel = channel_by_id.get(channel_id)
                if channel:
                    filtered_channels.append(channel)
                else:
                    invalid_channel_ids.append(channel_id)

            if not filtered_channels:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "team_id": team_id,
                        "message": "no syncable channels matched the requested channel_ids",
                        "requested_channel_ids": normalized_requested_channel_ids,
                    },
                )
            channels = filtered_channels

        tasks: list[SlackChannelSyncTask] = []
        for channel in channels:
            channel_id = channel.get("id")
            if not channel_id:
                continue

            channel_name = channel.get("name") or channel_id
            tasks.append(
                SlackChannelSyncTask(
                    sync_type="full",
                    event_id=uuid4().hex,
                    job_id=job_id,
                    team_id=team_id,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    sync_from=sync_from,
                    attempt=0,
                    max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
                    enqueued_at=enqueued_at,
                )
            )

        total_channels = len(tasks)
        job_meta = SyncJobMeta(
            job_id=job_id,
            team_id=team_id,
            sync_type="full",
            created_at=enqueued_at,
            total_channels=total_channels,
            queued_channels=total_channels,
        )
        await job_store.create_job(job_meta)
        job_created = True

        await runtime_events.append_event(
            job_id=job_id,
            team_id=team_id,
            event_type=SyncEventType.JOB_CREATED,
            payload={
                "total_channels": total_channels,
                "queued_channels": total_channels,
                "sync_type": "full",
                "sync_days": days,
                "requested_channel_count": (
                    len(normalized_requested_channel_ids)
                    if normalized_requested_channel_ids is not None
                    else None
                ),
                "invalid_channel_count": len(invalid_channel_ids),
            },
        )
        emit_job_accepted(
            job_id=job_id,
            team_id=team_id,
            total_channels=total_channels,
            queued_channels=total_channels,
            sync_type="full",
            trigger="api",
        )

        if tasks:
            await runtime_queue.enqueue_tasks(tasks)
            tasks_enqueued = True
        else:
            await job_store.mark_job_started(job_id)
            await runtime_events.append_event(
                job_id=job_id,
                team_id=team_id,
                event_type=SyncEventType.JOB_STARTED,
                payload={"total_channels": 0},
            )
            await job_store.mark_job_completed(
                job_id=job_id,
                failed_channels=0,
                last_error=None,
            )
            await runtime_events.append_event(
                job_id=job_id,
                team_id=team_id,
                event_type=SyncEventType.JOB_COMPLETED,
                payload={
                    "sync_type": "full",
                    "total_channels": 0,
                    "completed_channels": 0,
                    "failed_channels": 0,
                    "requeued_channels": 0,
                    "synced_messages": 0,
                    "flushed_events": 0,
                    "dropped_channels": 0,
                    "dropped_events": 0,
                },
            )
            emit_job_completed(
                job_id=job_id,
                team_id=team_id,
                total_channels=0,
                completed_channels=0,
                failed_channels=0,
                requeued_channels=0,
                total_synced_messages=0,
                sync_type="full",
                flushed_events=0,
                dropped_events=0,
                duration_ms=0,
            )
            await runtime_locks.release_team_lock_if_owner(team_id, job_id)
            lock_acquired = False

        base_url = str(request.base_url).rstrip("/")
        snapshot_url = f"{base_url}/api/v1/sync/jobs/{job_id}"
        stream_url = f"{base_url}/api/v1/sync/jobs/{job_id}/stream"

        return SlackFullSyncAcceptedResponse(
            job_id=job_id,
            team_id=team_id,
            total_channels=total_channels,
            queued_channels=total_channels,
            snapshot_url=snapshot_url,
            stream_url=stream_url,
        )

    except HTTPException:
        if lock_acquired and not tasks_enqueued:
            await runtime_locks.release_team_lock_if_owner(team_id, job_id)
        raise
    except Exception as e:
        logger.error(
            "[SLACK][FULL SYNC] Failed to enqueue full sync: team_id=%s, error=%s",
            team_id,
            e,
            exc_info=True,
        )

        if job_created and not tasks_enqueued:
            await job_store.update_job_fields(
                job_id,
                {
                    "status": SyncJobStatus.FAILED.value,
                    "started_at": enqueued_at,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": str(e),
                },
            )
            await runtime_events.append_event(
                job_id=job_id,
                team_id=team_id,
                event_type=SyncEventType.JOB_FAILED,
                payload={"error": str(e)},
            )
            emit_job_failed(
                job_id=job_id,
                team_id=team_id,
                failure_reason=SyncFailureReason.UNEXPECTED_ERROR.value,
                error_summary=str(e),
                sync_type="full",
            )

        if lock_acquired and not tasks_enqueued:
            await runtime_locks.release_team_lock_if_owner(team_id, job_id)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"동기화 요청 접수 중 오류 발생: {str(e)}",
        )


@router.post(
    "/flush",
    response_model=SlackIncrementalAcceptedResponse | SlackIncrementalNoEventsResponse,
)
async def flush_slack_buffers(
    flush_request: SlackIncrementalFlushRequest,
    request: Request,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    """
    팀 단위 Slack 증분 동기화 접수
    """
    team_id = flush_request.team_id
    logger.info("[SLACK][INCREMENTAL SYNC][API] Received flush request: team_id=%s", team_id)

    result = await enqueue_incremental_sync_job(
        db=db,
        team_id=team_id,
        base_url=str(request.base_url),
        trigger="api",
    )

    if result["status"] == "accepted":
        accepted = SlackIncrementalAcceptedResponse(
            job_id=result["job_id"],
            team_id=result["team_id"],
            total_channels=result["total_channels"],
            queued_channels=result["queued_channels"],
            dropped_channels=result["dropped_channels"],
            dropped_events=result["dropped_events"],
            snapshot_url=result["snapshot_url"] or "",
            stream_url=result["stream_url"] or "",
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=accepted.model_dump(),
        )

    if result["status"] == "no_events":
        return SlackIncrementalNoEventsResponse(
            team_id=result["team_id"],
            dropped_channels=result["dropped_channels"],
            dropped_events=result["dropped_events"],
            message=result["message"],
        )

    if result["status"] == "conflict":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "team_id": result["team_id"],
                "owner_job_id": result["owner_job_id"],
                "message": result["message"],
            },
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"증분 동기화 요청 접수 중 오류 발생: {result.get('message', 'unknown error')}",
    )


@router.get("/status", response_model=list[SlackSyncStatusResponse])
async def get_sync_status(
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
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
    _admin_user: User = Depends(require_admin_user),
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

        # channel_id를 가진 이벤트는 기존 채널 동기화 기록이 있을때만 처리
        event_channel_id = _extract_channel_id(event_type, event)
        if event_channel_id:
            channel_sync_state = slack_sync.get_channel_sync_state(
                db,
                team_id,
                event_channel_id,
            )
            if channel_sync_state is None:
                logger.info(
                    f"[SLACK][EVENT] Dropped event without channel sync state: "
                    f"team={team_id}, channel={event_channel_id}, type={event_type}, subtype={event_subtype}"
                )
                return {
                    "status": "dropped",
                    "reason": "missing_channel_sync_state",
                    "event_type": event_type,
                    "channel_id": event_channel_id,
                }

        # Message Event → Redis Buffer
        # bot_message subtype도 임베딩 동기화 대상으로 포함한다.
        if event_type == "message" and event_subtype in (None, "bot_message"):
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

def _extract_channel_id(event_type: str | None, event: dict) -> str | None:
    """Slack 이벤트 payload에서 채널 ID 추출"""
    if not event_type:
        return None

    channel = event.get("channel")
    if isinstance(channel, str):
        return channel

    if event_type in {"channel_created", "channel_rename", "group_created", "group_rename"}:
        if isinstance(channel, dict):
            channel_id = channel.get("id")
            if isinstance(channel_id, str):
                return channel_id
    return None


async def _handle_message_event(team_id: str, event: dict) -> dict:
    """
    Message Event를 Redis Buffer에 저장
    """
    try:
        data = SlackMessageEvent(**event)
    except Exception as e:
        logger.error(f"[SLACK][EVENT] Failed to Parse Message Event: {e}")
        return {"status": "error", "reason": "parse_failed"}

    # 작성자 user가 없는 경우에도 bot_message면 허용한다.
    if not data.user and data.subtype != "bot_message":
        logger.debug(
            f"[SLACK][EVENT] Ignored message without user: channel={data.channel}, ts={data.ts}"
        )
        return {"status": "skipped", "reason": "missing_user"}

    # 시스템 subtype은 제외하고, bot_message만 예외적으로 수집한다.
    if data.subtype is not None and data.subtype != "bot_message":
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
        f"channel={data.channel}, ts={data.ts}, user={data.user}, bot_id={data.bot_id}"
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
