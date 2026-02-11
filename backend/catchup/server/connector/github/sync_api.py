"""
GitHub Sync API Endpoints

GitHub 데이터 동기화 API.

Endpoints:
- POST /full: 전체 동기화
- POST /incremental: 증분 동기화
- GET /status/{installation_id}: 동기화 상태 조회
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from catchup.db.dependencies import get_db
from catchup.db.github import sync_repository as github_sync
from catchup.db.github import domain_repository as github_entities
from catchup.db.models import GitHubEntityType
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.service import GitHubIngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github/sync", tags=["github-sync"])


# ============================================================
# Request/Response Models
# ============================================================

class FullSyncRequest(BaseModel):
    """전체 동기화 요청"""
    installation_id: int = Field(..., description="GitHub App Installation ID")
    repo_ids: list[int] | None = Field(
        default=None,
        description="동기화할 Repository ID 목록. None이면 모든 접근 가능 레포"
    )
    sync_issues: bool = Field(default=True, description="Issue 동기화 여부")
    sync_prs: bool = Field(default=True, description="PR 동기화 여부 (Commits 포함)")
    branch: str | None = Field(
        default=None,
        description="코드베이스 동기화 대상 브랜치 (향후 구현 예정)"
    )


class IncrementalSyncRequest(BaseModel):
    """증분 동기화 요청"""
    installation_id: int = Field(..., description="GitHub App Installation ID")
    repo_ids: list[int] | None = Field(
        default=None,
        description="동기화할 Repository ID 목록. None이면 모든 접근 가능 레포"
    )


class SyncResult(BaseModel):
    """동기화 결과"""
    synced: int
    errors: int


class SyncResponse(BaseModel):
    """동기화 응답"""
    success: bool
    message: str
    results: dict[str, SyncResult]


class SyncStateResponse(BaseModel):
    """동기화 상태 응답"""
    installation_id: int
    repositories: list[dict[str, Any]]


# ============================================================
# Helper Functions
# ============================================================

async def _get_ingestion_service(
    db: Session,
    installation_id: int,
) -> GitHubIngestionService:
    """GitHubIngestionService 인스턴스 생성"""
    # Installation 정보 확인
    installation = get_installation_by_installation_id(db, installation_id)
    if not installation:
        raise HTTPException(
            status_code=404,
            detail=f"GitHub Installation not found: {installation_id}"
        )

    # Installation Access Token 발급
    github_app_service = get_github_app_service()
    access_token = await github_app_service.get_installation_access_token(installation_id)

    # Service 인스턴스 생성 및 초기화
    service = GitHubIngestionService(installation_id, access_token)
    await service.initialize()

    return service


# ============================================================
# Endpoints
# ============================================================

@router.post("/full", response_model=SyncResponse)
async def full_sync(
    request: FullSyncRequest,
    db: Session = Depends(get_db),
):
    """
    전체 동기화 수행

    Issue와 PR을 동기화합니다. (PR에 Commits 포함)
    """
    try:
        service = await _get_ingestion_service(db, request.installation_id)

        results = await service.full_sync(
            db=db,
            repo_ids=request.repo_ids,
            sync_issues=request.sync_issues,
            sync_prs=request.sync_prs,
            branch=request.branch,
        )

        return SyncResponse(
            success=True,
            message="Full sync completed",
            results={
                k: SyncResult(**v) for k, v in results.items()
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/incremental", response_model=SyncResponse)
async def incremental_sync(
    request: IncrementalSyncRequest,
    db: Session = Depends(get_db),
):
    """
    증분 동기화 수행

    마지막 동기화 이후 변경된 데이터만 동기화합니다.
    """
    try:
        service = await _get_ingestion_service(db, request.installation_id)

        results = await service.incremental_sync(
            db=db,
            repo_ids=request.repo_ids,
        )

        return SyncResponse(
            success=True,
            message="Incremental sync completed",
            results={
                k: SyncResult(**v) for k, v in results.items()
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Incremental sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{installation_id}", response_model=SyncStateResponse)
async def get_sync_status(
    installation_id: int,
    db: Session = Depends(get_db),
):
    """
    동기화 상태 조회

    Installation의 모든 Repository별 동기화 상태를 반환합니다.
    """
    try:
        # Installation 정보 확인
        installation = get_installation_by_installation_id(db, installation_id)
        if not installation:
            raise HTTPException(
                status_code=404,
                detail=f"GitHub Installation not found: {installation_id}"
            )

        # 모든 동기화 상태 조회
        sync_states = github_sync.get_installation_sync_states(db, installation_id)

        # Repository 별로 그룹화
        repos_data: dict[str, dict] = {}
        for state in sync_states:
            repo_name = state.repository_full_name
            if repo_name not in repos_data:
                repos_data[repo_name] = {
                    "repository": repo_name,
                    "entities": {},
                }

            repos_data[repo_name]["entities"][state.entity_type] = {
                "status": state.last_sync_status,
                "synced_count": state.synced_entities,
                "total_count": state.total_entities,
                "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
                "last_successful_sync_at": state.last_successful_sync_at.isoformat() if state.last_successful_sync_at else None,
                "error": state.last_sync_error,
            }

        return SyncStateResponse(
            installation_id=installation_id,
            repositories=list(repos_data.values()),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repositories/{installation_id}")
async def list_repositories(
    installation_id: int,
    db: Session = Depends(get_db),
):
    """
    Installation에서 접근 가능한 Repository 목록 조회

    RDBMS에 저장된 Repository 정보를 반환합니다.
    """
    try:
        # Installation 정보 확인
        installation = get_installation_by_installation_id(db, installation_id)
        if not installation:
            raise HTTPException(
                status_code=404,
                detail=f"GitHub Installation not found: {installation_id}"
            )

        # Repository 목록 조회
        repos = github_entities.get_repositories_by_installation(db, installation_id)

        return {
            "installation_id": installation_id,
            "repositories": [
                {
                    "id": repo.repo_id,
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "default_branch": repo.default_branch,
                    "language": repo.language,
                    "private": repo.private,
                    "archived": repo.archived,
                    "html_url": repo.html_url,
                    "synced_at": repo.synced_at.isoformat() if repo.synced_at else None,
                }
                for repo in repos
            ],
            "total": len(repos),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repositories/{installation_id}/refresh")
async def refresh_repositories(
    installation_id: int,
    db: Session = Depends(get_db),
):
    """
    GitHub API에서 Repository 목록을 다시 가져와 RDBMS에 저장

    Installation의 접근 가능한 Repository 목록을 최신 상태로 갱신합니다.
    새로 추가된 레포가 있거나 권한이 변경된 경우 사용합니다.
    """
    try:
        service = await _get_ingestion_service(db, installation_id)

        # GitHub API에서 레포 목록 조회
        repos_data = await service.client.list_installation_repos()

        # RDBMS에 벌크 저장
        count = github_entities.upsert_repositories_bulk(db, installation_id, repos_data)

        logger.info(f"Refreshed {count} repositories for installation {installation_id}")

        # 갱신된 목록 반환
        repos = github_entities.get_repositories_by_installation(db, installation_id)

        return {
            "installation_id": installation_id,
            "message": f"Refreshed {count} repositories from GitHub",
            "repositories": [
                {
                    "id": repo.repo_id,
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "default_branch": repo.default_branch,
                    "language": repo.language,
                    "private": repo.private,
                    "archived": repo.archived,
                    "html_url": repo.html_url,
                    "synced_at": repo.synced_at.isoformat() if repo.synced_at else None,
                }
                for repo in repos
            ],
            "total": len(repos),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
