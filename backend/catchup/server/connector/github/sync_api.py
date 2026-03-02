"""
Github Sync API Endpoints

Github 데이터 동기화 API.

Endpoints:
- POST /full: 전체 동기화
- GET /status?installation_id=: 동기화 상태 조회
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.db.models import User
from catchup.db.dependencies import get_db
from catchup.db.github import sync_repository as github_sync
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.domain_repository import RepositoryUpsertData
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.service import GithubIngestionService
from catchup.server.connector.sync_status.schemas import (
    ConnectorSyncScope,
    ConnectorSyncStatusResponse,
    build_empty_entity_status,
    build_entity_status,
)
from catchup.utils.scheduler import flush_github_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github/sync", tags=["github-sync"])




# ============================================================
# Request/Response Models
# ============================================================

class FullSyncRequest(BaseModel):
    """전체 동기화 요청"""
    installation_id: int = Field(..., description="Github App Installation ID")
    repo_ids: list[int] | None = Field(
        default=None,
        description="동기화할 Repository ID 목록. None이면 모든 접근 가능 레포"
    )
    sync_days: int | None = Field(
        default=None,
        description="수집 범위 (일), 미지정 시 기본값 사용",
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

class AccessibleRepositoryItem(BaseModel):
    """
    접근 가능한 Repository
    """
    repo_id: int
    full_name: str

class AccessibleRepositoriesResponse(BaseModel):
    installation_id: int
    total_repositories: int
    repositories: list[AccessibleRepositoryItem]

# ============================================================
# Helper Functions
# ============================================================

async def _get_ingestion_service(
    db: Session,
    installation_id: int,
) -> GithubIngestionService:
    """GithubIngestionService 인스턴스 생성"""
    # Installation 정보 확인
    installation = get_installation_by_installation_id(db, installation_id)
    if not installation:
        raise HTTPException(
            status_code=404,
            detail=f"Github Installation not found: {installation_id}"
        )

    # Installation Access Token 발급
    github_app_service = get_github_app_service()
    access_token = await github_app_service.get_installation_access_token(installation_id)

    # Service 인스턴스 생성 및 초기화
    repository = PGVectorRepository(
        embeddings=get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    )
    
    service = GithubIngestionService(
        repository=repository,
        installation_id=installation_id,
        access_token=access_token
    )
    await service.initialize()

    return service


# ============================================================
# Endpoints
# ============================================================

@router.post("/full", response_model=SyncResponse)
async def full_sync(
    request: FullSyncRequest,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
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
            sync_days=request.sync_days,
        )
        logger.info(
            "[GITHUB][FULL SYNC] full_sync completed: "
            f"installation_id={request.installation_id}, results={results}"
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
        logger.error(
            "[GITHUB][FULL SYNC] full_sync failed: "
            f"installation_id={request.installation_id}, error={e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=ConnectorSyncStatusResponse)
async def get_sync_status(
    installation_id: int = Query(..., description="Github App Installation ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
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

        sync_states = github_sync.get_installation_sync_states(db, installation_id)
        fixed_entity_types = ("issue", "pull_request")

        scopes_by_repo: dict[str, ConnectorSyncScope] = {}
        for state in sync_states:
            entity_type = str(state.entity_type)
            if entity_type not in fixed_entity_types:
                continue

            repo_name = state.repository_full_name
            if repo_name not in scopes_by_repo:
                scopes_by_repo[repo_name] = ConnectorSyncScope(
                    scope_id=repo_name,
                    scope_name=repo_name,
                    entities={
                        "issue": build_empty_entity_status(total_count=0),
                        "pull_request": build_empty_entity_status(total_count=0),
                    },
                )

            scopes_by_repo[repo_name].entities[entity_type] = build_entity_status(
                status=state.last_sync_status,
                synced_count=state.synced_entities or 0,
                total_count=state.total_entities or 0,
                last_sync_at=state.last_sync_at,
                last_successful_sync_at=state.last_successful_sync_at,
                error=state.last_sync_error,
            )

        scopes = list(scopes_by_repo.values())
        logger.info(
            "[GITHUB][SYNC STATUS] fetched: installation_id=%s, scopes=%s",
            installation_id,
            len(scopes),
        )

        return ConnectorSyncStatusResponse(
            source="github",
            target_id=str(installation_id),
            scopes=scopes,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[GITHUB][SYNC STATUS] get_sync_status failed: "
            f"installation_id={installation_id}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repositories/{installation_id}")
async def list_repositories(
    installation_id: int,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
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
        logger.error(
            "[GITHUB][SYNC] list_repositories failed: "
            f"installation_id={installation_id}, error={e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repositories/{installation_id}/refresh")
async def refresh_repositories(
    installation_id: int,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    """
    GitHub API에서 Repository 목록을 다시 가져와 RDBMS에 저장

    Installation의 접근 가능한 Repository 목록을 최신 상태로 갱신합니다.
    새로 추가된 레포가 있거나 권한이 변경된 경우 사용합니다.
    """
    try:
        service = await _get_ingestion_service(db, installation_id)

        # GitHub API에서 레포 목록 조회
        raw_repos = await service.client.list_installation_repos()

        # dict → DTO 변환 후 RDBMS에 벌크 저장
        repos_data = [
            RepositoryUpsertData(
                repo_id=repo.get("id", 0),
                owner=repo.get("owner", {}).get("login", ""),
                name=repo.get("name", ""),
                full_name=repo.get("full_name", ""),
                html_url=repo.get("html_url", ""),
                description=repo.get("description"),
                default_branch=repo.get("default_branch", "main"),
                language=repo.get("language"),
                topics=repo.get("topics", []),
                stargazers_count=repo.get("stargazers_count", 0),
                forks_count=repo.get("forks_count", 0),
                open_issues_count=repo.get("open_issues_count", 0),
                private=repo.get("private", False),
                archived=repo.get("archived", False),
                disabled=repo.get("disabled", False),
                pushed_at=repo.get("pushed_at"),
                repo_created_at=repo.get("created_at"),
                repo_updated_at=repo.get("updated_at"),
            )
            for repo in raw_repos
        ]
        count = github_entities.upsert_repositories_bulk(db, installation_id, repos_data)

        logger.info(
            "[GITHUB][SYNC] refresh_repositories completed: "
            f"installation_id={installation_id}, refreshed_count={count}"
        )

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
        logger.error(
            "[GITHUB][SYNC] refresh_repositories failed: "
            f"installation_id={installation_id}, error={e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flush")
async def test_flush_webhook_events(
    _admin_user: User = Depends(require_admin_user),
):
    """
    Redis에 저장하고 있는 Github Webhook 이벤트들을 즉시 동기화합니다.
    - APScheduler가 1시간 단위로 수행하고 있는 Task를 동작시킵니다.
    """
    try:
        logger.info("[GITHUB][FLUSH] Manually flushing GitHub webhook events")
        await flush_github_events()

        return {
            "success": True,
            "message": "[GITHUB][FLUSH] Successed Github Webhook Event Flush"
        }

    except Exception as e:
        logger.error(f"Manual webhook flush failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/accessible/repositories", response_model=AccessibleRepositoriesResponse)
async def list_accessible_repositories(
    installation_id: int = Query(..., description="Github App Installation ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    try:
        installation = get_installation_by_installation_id(db, installation_id)
        if not installation:
            raise HTTPException(
                status_code = 404,
                detail = f"Github Installation Not Found: {installation_id}",
            )
        
        service = await _get_ingestion_service(db, installation_id)
        raw_repos = await service.client.list_installation_repos()

        repo_map: dict[int, RepositoryUpsertData] = {}
        for repo in raw_repos:
            repo_id = repo.get("id")
            full_name = repo.get("full_name")
            owner = (repo.get("owner") or {}).get("login")
            name = repo.get("name")
            html_url = repo.get("html_url")

            if not repo_id or not full_name or not owner or not name or not html_url:
                logger.debug(
                    "[GITHUB][FULL SYNC][ACCESSIBLE] Skip invalid repository payload: installation_id=%s, repo_id=%s, full_name=%s",
                    installation_id,
                    repo_id,
                    full_name,
                )
                continue

            repo_map[int(repo_id)] = RepositoryUpsertData(
                repo_id=int(repo_id),
                owner=owner,
                name=name,
                full_name=full_name,
                html_url=html_url,
                description=repo.get("description"),
                default_branch=repo.get("default_branch", "main"),
                language=repo.get("language"),
                topics=repo.get("topics", []),
                stargazers_count=repo.get("stargazers_count", 0),
                forks_count=repo.get("forks_count", 0),
                open_issues_count=repo.get("open_issues_count", 0),
                private=repo.get("private", False),
                archived=repo.get("archived", False),
                disabled=repo.get("disabled", False),
                pushed_at=repo.get("pushed_at"),
                repo_created_at=repo.get("created_at"),
                repo_updated_at=repo.get("updated_at"),
            )

        repos_data = list(repo_map.values())
        
        sync_result = github_entities.sync_repositories_snapshot(
            db = db,
            installation_id = installation_id,
            repos_data=repos_data,
        )

        repositories = [
            AccessibleRepositoryItem(repo_id=repo.repo_id, full_name = repo.full_name)
            for repo in repos_data
        ]
        repositories.sort(key=lambda item: item.full_name.lower())

        logger.info(
            "[GITHUB][FULL SYNC][ACCESSIBLE] Accessible repositories synced: installation_id=%s, fetched=%s, upserted=%s, deleted=%s",
            installation_id,
            len(repositories),
            sync_result["upserted"],
            sync_result["deleted"],
        )

        return AccessibleRepositoriesResponse(
            installation_id=installation_id,
            total_repositories=len(repositories),
            repositories=repositories,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[GITHUB][FULL SYNC][ACCESSIBLE] list_accessible_repositories failed: installation_id=%s, error=%s",
            installation_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="접근 가능한 Repository 조회 중 오류가 발생했습니다.",
        )
