"""
Jira Sync API

Jira 데이터 동기화 API 엔드포인트.
전체/증분 동기화, 상태 조회 기능 제공.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.db.jira import sync_repository as jira_sync
from catchup.db.atlassian.oauth_repository import get_all_tokens
from catchup.db.dependencies import get_db
from catchup.db.models import User, UserRole
from catchup.db.models import JiraEntityType, JiraSyncState
from catchup.utils.webhook_buffer import get_webhook_buffer

logger = logging.getLogger(__name__)


# ================================================================
# Request/Response Schemas
# ================================================================

class SyncRequest(BaseModel):
    """동기화 요청 (최소 파라미터)"""
    cloud_id: str = Field(..., description="Jira Cloud ID")
    project_keys: list[str] | None = Field(
        None,
        description="동기화할 프로젝트 키 목록 (None이면 전체)",
        examples=[["CATCH", "PROJ"]],
    )
    sync_days: int | None = Field(
        None,
        description="수집 범위 (일), 미지정 시 기본값 사용",
    )


class SyncResultDetail(BaseModel):
    """엔티티별 동기화 결과"""
    synced: int = 0
    errors: int = 0


class SyncResponse(BaseModel):
    """동기화 응답"""
    status: str
    message: str
    cloud_id: str | None = None
    results: dict[str, SyncResultDetail] | None = Field(
        None,
        description="엔티티별 동기화 결과 (issues, epics, projects, sprints)",
    )


class SyncStatusResponse(BaseModel):
    """동기화 상태 응답"""
    cloud_id: str
    entity_type: str
    last_sync_status: str | None
    last_successful_sync_at: str | None
    synced_entities: int
    last_sync_error: str | None


# ================================================================
# Flush Response Schemas
# ================================================================

class JiraFlushCloudResult(BaseModel):
    """클라우드별 Flush 결과"""
    cloud_id: str
    site_name: str | None = None
    flushed_projects: int
    failed_projects: int
    flushed_events: int
    synced_entities: int
    deleted_documents: int
    status: str  # "success" | "no_events" | "error"
    error_message: str | None = None


class JiraFlushResponse(BaseModel):
    """전체 Flush 응답"""
    status: str
    message: str
    total_clouds: int = Field(description="처리 대상 Cloud 수")
    flushed_clouds: int = Field(description="실제로 flush된 Cloud 수")
    total_projects: int = Field(description="실제로 flush된 프로젝트 수")
    total_events: int = Field(description="총 flush된 이벤트 수")
    total_synced: int = Field(description="총 동기화된 엔티티 수")
    total_deleted_documents: int = Field(description="삭제된 문서 수")
    results: list[JiraFlushCloudResult] = Field(default_factory=list)


# ================================================================
# Router
# ================================================================

router = APIRouter(prefix="/api/v1/jira/sync", tags=["jira-sync"])


def _require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Jira 동기화 API 접근 권한 검사.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="권한이 없습니다. 관리자만 동기화 API를 호출할 수 있습니다.",
        )
    return current_user


# ================================================================
# Endpoints
# ================================================================

@router.post("/full", response_model=SyncResponse)
async def trigger_full_sync(
    request: SyncRequest,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(_require_admin_user),
):
    """
    전체 동기화 트리거

    지정된 프로젝트(또는 전체)의 모든 Jira 데이터를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.

    """
    cloud_id = request.cloud_id
    try:
        service = await create_jira_ingestion_service(db, cloud_id)
        result = await service.full_sync(
            db=db,
            project_keys=request.project_keys,
            sync_days=request.sync_days,
        )

        summary_parts = []
        if result["issues"]["synced"] > 0 or result["issues"]["errors"] > 0:
            summary_parts.append(f"Issues={result['issues']['synced']}")
        if result["epics"]["synced"] > 0 or result["epics"]["errors"] > 0:
            summary_parts.append(f"Epics={result['epics']['synced']}")
        if result["projects"]["synced"] > 0 or result["projects"]["errors"] > 0:
            summary_parts.append(f"Projects={result['projects']['synced']}")
        if result["sprints"]["synced"] > 0 or result["sprints"]["errors"] > 0:
            summary_parts.append(f"Sprints={result['sprints']['synced']}")
        if result["users"]["synced"] > 0 or result["users"]["errors"] > 0:
            summary_parts.append(f"Users={result['users']['synced']}")

        message = f"전체 동기화 완료: {', '.join(summary_parts)}" if summary_parts else "동기화할 데이터가 없습니다"

        return SyncResponse(
            status="success",
            message=message,
            cloud_id=cloud_id,
            results={
                "issues": SyncResultDetail(**result["issues"]),
                "epics": SyncResultDetail(**result["epics"]),
                "projects": SyncResultDetail(**result["projects"]),
                "sprints": SyncResultDetail(**result["sprints"]),
                "users": SyncResultDetail(**result["users"]),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full sync error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
        )


@router.post("/flush", response_model=JiraFlushResponse)
async def flush_all_jira_buffers(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(_require_admin_user),
):
    """
    모든 Jira Cloud의 Redis 버퍼를 즉시 flush하고 증분 동기화

    스케줄러가 주기적으로 실행하는 flush 로직을 수동으로 트리거합니다.
    """
    logger.info("[JIRA][FLUSH] Starting manual Jira webhook flush for all clouds")

    buffer = get_webhook_buffer()
    results: list[JiraFlushCloudResult] = []
    total_projects = 0
    total_events = 0
    total_synced = 0
    total_deleted_documents = 0
    flushed_clouds_count = 0

    try:
        # 1) 연결된 전체 Jira Cloud 조회
        tokens = get_all_tokens(db)
        if not tokens:
            logger.info("[JIRA][FLUSH] No Jira tokens found")
            return JiraFlushResponse(
                status="success",
                message="연결된 Jira Cloud가 없습니다",
                total_clouds=0,
                flushed_clouds=0,
                total_projects=0,
                total_events=0,
                total_synced=0,
                total_deleted_documents=0,
            )

        logger.info(f"[JIRA][FLUSH] Found clouds: count={len(tokens)}")

        # 2) Cloud 단위로 버퍼 flush + 증분 동기화
        for token in tokens:
            cloud_id = token.cloud_id
            site_name = token.site_name

            try:
                projects_with_events = await buffer.get_jira_buffered_projects(cloud_id)
                if not projects_with_events:
                    logger.debug(f"[JIRA][FLUSH] No buffered events: cloud_id={cloud_id}")
                    results.append(
                        JiraFlushCloudResult(
                            cloud_id=cloud_id,
                            site_name=site_name,
                            flushed_projects=0,
                            failed_projects=0,
                            flushed_events=0,
                            synced_entities=0,
                            deleted_documents=0,
                            status="no_events",
                        )
                    )
                    continue

                logger.info(
                    f"[JIRA][FLUSH] Buffered projects found: "
                    f"cloud_id={cloud_id}, projects={len(projects_with_events)}"
                )

                # 3) 프로젝트별 증분 동기화 기준 시각 확보
                issue_sync_state = jira_sync.get_sync_state(db, cloud_id, JiraEntityType.ISSUE)
                base_since = (
                    issue_sync_state.last_successful_sync_at
                    if issue_sync_state and issue_sync_state.last_successful_sync_at
                    else None
                )

                service = await create_jira_ingestion_service(db, cloud_id)

                cloud_flushed_projects = 0
                cloud_failed_projects = 0
                cloud_events = 0
                cloud_synced = 0
                cloud_deleted_documents = 0
                first_error_message: str | None = None

                # 4) 프로젝트 단위로 이벤트 정규화 후 증분 동기화
                for project_key in projects_with_events:
                    try:
                        events = await buffer.get_jira_project_events(cloud_id, project_key)
                        if not events:
                            logger.debug(
                                f"[JIRA][FLUSH] Empty project buffer: "
                                f"cloud_id={cloud_id}, project_key={project_key}"
                            )
                            continue

                        latest_event_by_issue: dict[str, dict] = {}
                        for event in events:
                            issue_key = event.get("key")
                            event_type = event.get("type")
                            if not issue_key or not event_type:
                                continue

                            event_ts = float(event.get("timestamp") or 0.0)
                            previous = latest_event_by_issue.get(issue_key)
                            if previous is None or event_ts >= previous["timestamp"]:
                                latest_event_by_issue[issue_key] = {
                                    "type": event_type,
                                    "timestamp": event_ts,
                                }

                        if not latest_event_by_issue:
                            logger.debug(
                                f"[JIRA][FLUSH] No valid events after normalize: "
                                f"cloud_id={cloud_id}, project_key={project_key}"
                            )
                            continue

                        event_types = {value["type"] for value in latest_event_by_issue.values()}
                        deleted_issue_keys = sorted(
                            issue_key
                            for issue_key, value in latest_event_by_issue.items()
                            if value["type"] == "jira:issue_deleted"
                        )

                        sync_result = await service.incremental_sync(
                            db=db,
                            since=base_since,
                            project_keys=[project_key],
                            event_types=event_types,
                        )

                        deleted_doc_count = 0
                        if deleted_issue_keys:
                            deleted_doc_count = await service.delete_issue_documents(deleted_issue_keys)

                        cleared_event_count = await buffer.clear_jira_buffer(cloud_id, project_key)

                        cloud_flushed_projects += 1
                        cloud_events += cleared_event_count
                        cloud_synced += int(sync_result.get("issues", 0)) + int(sync_result.get("epics", 0))
                        cloud_deleted_documents += deleted_doc_count

                        logger.info(
                            f"[JIRA][FLUSH] Project synced: "
                            f"cloud_id={cloud_id}, project_key={project_key}, "
                            f"events={cleared_event_count}, event_types={sorted(event_types)}, "
                            f"sync_result={sync_result}, deleted_docs={deleted_doc_count}"
                        )
                    except Exception as e:
                        cloud_failed_projects += 1
                        if first_error_message is None:
                            first_error_message = str(e)
                        logger.error(
                            f"[JIRA][FLUSH] Project sync failed (buffer kept): "
                            f"cloud_id={cloud_id}, project_key={project_key}, error={e}",
                            exc_info=True,
                        )

                if cloud_flushed_projects > 0:
                    cloud_status = "success"
                    flushed_clouds_count += 1
                    total_projects += cloud_flushed_projects
                    total_events += cloud_events
                    total_synced += cloud_synced
                    total_deleted_documents += cloud_deleted_documents
                elif cloud_failed_projects > 0:
                    cloud_status = "error"
                else:
                    cloud_status = "no_events"

                results.append(
                    JiraFlushCloudResult(
                        cloud_id=cloud_id,
                        site_name=site_name,
                        flushed_projects=cloud_flushed_projects,
                        failed_projects=cloud_failed_projects,
                        flushed_events=cloud_events,
                        synced_entities=cloud_synced,
                        deleted_documents=cloud_deleted_documents,
                        status=cloud_status,
                        error_message=first_error_message if cloud_status == "error" else None,
                    )
                )
            except Exception as e:
                logger.error(
                    f"[JIRA][FLUSH] Cloud flush failed: cloud_id={cloud_id}, error={e}",
                    exc_info=True,
                )
                results.append(
                    JiraFlushCloudResult(
                        cloud_id=cloud_id,
                        site_name=site_name,
                        flushed_projects=0,
                        failed_projects=0,
                        flushed_events=0,
                        synced_entities=0,
                        deleted_documents=0,
                        status="error",
                        error_message=str(e),
                    )
                )

        message = (
            f"전체 flush 완료: {len(tokens)}개 Cloud 중 {flushed_clouds_count}개 처리, "
            f"{total_projects}개 프로젝트, {total_events}개 이벤트, "
            f"{total_synced}개 엔티티 동기화, {total_deleted_documents}개 문서 삭제"
        )
        logger.info(f"[JIRA][FLUSH] Manual flush completed: {message}")

        return JiraFlushResponse(
            status="success",
            message=message,
            total_clouds=len(tokens),
            flushed_clouds=flushed_clouds_count,
            total_projects=total_projects,
            total_events=total_events,
            total_synced=total_synced,
            total_deleted_documents=total_deleted_documents,
            results=results,
        )

    except Exception as e:
        logger.error(f"[JIRA][FLUSH] Flush all error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"전체 flush 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/status", response_model=list[SyncStatusResponse])
async def get_sync_status(
    cloud_id: str = Query(..., description="Jira Cloud ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(_require_admin_user),
):
    """
    동기화 상태 조회

    해당 Jira 인스턴스의 엔티티별 동기화 상태를 반환.
    """
    stmt = select(JiraSyncState).where(JiraSyncState.cloud_id == cloud_id)
    result = db.execute(stmt)
    sync_states = result.scalars().all()

    if not sync_states:
        return []

    return [
        SyncStatusResponse(
            cloud_id=state.cloud_id,
            entity_type=state.entity_type,
            last_sync_status=state.last_sync_status,
            last_successful_sync_at=(
                state.last_successful_sync_at.isoformat()
                if state.last_successful_sync_at
                else None
            ),
            synced_entities=state.synced_entities or 0,
            last_sync_error=state.last_sync_error,
        )
        for state in sync_states
    ]
