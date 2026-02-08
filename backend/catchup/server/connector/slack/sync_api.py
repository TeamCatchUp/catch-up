"""
Slack Sync API

Slack 데이터 동기화 API 엔드포인트.
전체/증분 동기화, 상태 조회, 검색 기능 제공.

사용법:
    POST /api/v1/slack/sync/full?team_id=T123ABC
    POST /api/v1/slack/sync/incremental?team_id=T123ABC
    GET  /api/v1/slack/sync/status?team_id=T123ABC
    POST /api/v1/slack/sync/search?team_id=T123ABC
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.db.dependencies import get_db
from catchup.db.models import SlackSyncState

logger = logging.getLogger(__name__)


# ================================================================
# Request/Response Schemas
# ================================================================

class SlackSyncRequest(BaseModel):
    """
    동기화 요청

    저장소 분리:
    - Message: PGVector (Vector Store) - 시맨틱 검색용
    - Workspace, Channel, User: RDBMS - 정적 참조 데이터
    - File: Message에 통합 (message_type="file_share")
    """
    oldest: str | None = Field(
        None,
        description="시작 Slack timestamp (이 시간 이후 메시지만)",
        examples=["1704067200.000000"],
    )
    latest: str | None = Field(
        None,
        description="종료 Slack timestamp (이 시간 이전 메시지만)",
    )
    channel_ids: list[str] | None = Field(
        None,
        description="동기화할 채널 ID 목록 (None이면 전체)",
        examples=[["C123ABC", "C456DEF"]],
    )
    sync_messages: bool = Field(True, description="메시지 동기화 여부 (Vector Store)")
    sync_channels: bool = Field(True, description="채널 동기화 여부 (RDBMS)")
    sync_users: bool = Field(True, description="사용자 동기화 여부 (RDBMS)")
    sync_workspace: bool = Field(True, description="워크스페이스 동기화 여부 (RDBMS)")


class SyncResultDetail(BaseModel):
    """엔티티별 동기화 결과"""
    synced: int = 0
    errors: int = 0
    skipped: int = 0


class SlackSyncResponse(BaseModel):
    """동기화 응답"""
    status: str
    message: str
    team_id: str | None = None
    results: dict[str, SyncResultDetail] | None = Field(
        None,
        description="엔티티별 동기화 결과 (messages, channels, users, workspace)",
    )


class SlackSyncStatusResponse(BaseModel):
    """동기화 상태 응답"""
    team_id: str
    entity_type: str
    last_sync_status: str | None
    last_successful_sync_at: str | None
    synced_entities: int
    last_sync_error: str | None
    oldest_ts: str | None = None
    latest_ts: str | None = None


class SlackSearchRequest(BaseModel):
    """검색 요청 (Message만 Vector Store에 저장됨)"""
    query: str = Field(..., description="검색 쿼리 (자연어)")
    k: int = Field(5, ge=1, le=50, description="반환할 결과 수")
    channel_id: str | None = Field(None, description="채널 필터")


class SearchResultItem(BaseModel):
    """검색 결과 항목"""
    id: str
    content: str
    metadata: dict[str, Any]


class SlackSearchResponse(BaseModel):
    """검색 응답"""
    results: list[SearchResultItem]
    total: int


# ================================================================
# Router
# ================================================================

router = APIRouter(prefix="/api/v1/slack/sync", tags=["slack-sync"])


@router.post("/full", response_model=SlackSyncResponse)
async def trigger_full_sync(
    request: SlackSyncRequest,
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
):
    """
    전체 동기화 트리거

    지정된 채널(또는 전체)의 모든 Slack 데이터를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    try:
        service = await create_slack_ingestion_service(db, team_id)

        result = await service.full_sync(
            db,
            oldest=request.oldest,
            latest=request.latest,
            channel_ids=request.channel_ids,
            sync_messages=request.sync_messages,
            sync_channels=request.sync_channels,
            sync_users=request.sync_users,
            sync_workspace=request.sync_workspace,
        )

        # 결과 메시지 생성
        summary_parts = []
        skipped_count = 0
        for entity_type, entity_result in result.items():
            if entity_result.get("synced", 0) > 0 or entity_result.get("errors", 0) > 0:
                summary_parts.append(f"{entity_type.capitalize()}={entity_result['synced']}")
            skipped_count += entity_result.get("skipped", 0)

        message = (
            f"전체 동기화 완료: {', '.join(summary_parts)}"
            if summary_parts
            else "동기화할 데이터가 없습니다"
        )
        if skipped_count > 0:
            message += f" (Skipped: {skipped_count} channels)"

        return SlackSyncResponse(
            status="success",
            message=message,
            team_id=team_id,
            results={
                entity_type: SyncResultDetail(
                    synced=entity_result.get("synced", 0),
                    errors=entity_result.get("errors", 0),
                    skipped=entity_result.get("skipped", 0),
                )
                for entity_type, entity_result in result.items()
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full sync error for team_id={team_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
        )


@router.post("/incremental", response_model=SlackSyncResponse)
async def trigger_incremental_sync(
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
):
    """
    증분 동기화 트리거

    마지막 동기화 이후 업데이트된 데이터만 동기화.
    이전 동기화 기록이 없으면 전체 동기화로 전환됩니다.
    """
    try:
        service = await create_slack_ingestion_service(db, team_id)
        result = await service.incremental_sync(db)

        # 결과 메시지 생성
        summary_parts = []
        for entity_type, entity_result in result.items():
            if entity_result["synced"] > 0:
                summary_parts.append(f"{entity_type.capitalize()}={entity_result['synced']}")

        message = (
            f"증분 동기화 완료: {', '.join(summary_parts)}"
            if summary_parts
            else "동기화할 변경사항이 없습니다"
        )

        return SlackSyncResponse(
            status="success",
            message=message,
            team_id=team_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Incremental sync error for team_id={team_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
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


class ChannelAccessInfo(BaseModel):
    """채널 접근 정보"""
    id: str
    name: str
    channel_type: str
    is_member: bool
    is_private: bool
    member_count: int | None = None


class ChannelAccessResponse(BaseModel):
    """채널 접근 권한 디버그 응답"""
    team_id: str
    total_channels: int
    accessible_channels: int
    channels: list[ChannelAccessInfo]


@router.get("/debug/channels", response_model=ChannelAccessResponse)
async def debug_channel_access(
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
):
    """
    [디버그] Bot이 접근 가능한 채널 목록 조회

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


@router.post("/search", response_model=SlackSearchResponse)
async def search_slack_documents(
    request: SlackSearchRequest,
    team_id: str = Query(..., description="Slack Team/Workspace ID"),
    db: Session = Depends(get_db),
):
    """
    Slack 메시지 벡터 검색

    PGVector에 저장된 Slack 메시지에서 시맨틱 검색 수행.
    (Workspace, Channel, User는 RDBMS에 저장되어 벡터 검색 대상 아님)
    """
    try:
        service = await create_slack_ingestion_service(db, team_id)

        documents = await service.search(
            query=request.query,
            k=request.k,
            entity_type="message",  # 메시지만 Vector Store에 저장
            channel_id=request.channel_id,
        )

        results = [
            SearchResultItem(
                id=doc.id or "",
                content=doc.page_content[:500],  # 500자로 제한
                metadata=doc.metadata,
            )
            for doc in documents
        ]

        return SlackSearchResponse(results=results, total=len(results))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error for team_id={team_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}",
        )
