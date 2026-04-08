"""
Atlassian Auth API

Atlassian OAuth 통합 인증 API 엔드포인트.
하나의 OAuth 앱으로 Jira + Confluence 접근 권한을 획득한다.
"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy import select

from catchup.audit.actions import IntegrationAction
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connectors.atlassian.oauth_client import (
    AtlassianOAuthClient,
    get_atlassian_oauth_client,
)
from catchup.connectors.atlassian.exceptions import AtlassianError
from catchup.connectors.atlassian.callback_service import (
    AtlassianCallbackService,
    CallbackError,
)
from catchup.connectors.atlassian.token_manager import (
    AtlassianTokenManager,
    AtlassianTokenProvider,
)
from catchup.connectors.confluence.metadata_service import ConfluenceMetadataService
from catchup.connectors.atlassian.schemas import AtlassianInstallationStatus
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.jira.dynamic_webhook_service import (
    get_jira_dynamic_webhook_service,
)
from catchup.configs.config import auth_settings
from catchup.db.engine import SessionLocal
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import KnowledgeSource, SourceType
from catchup.db.workspaces import get_workspace_limit_one
from catchup.utils.redis import store_oauth_state

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/auth/atlassian", tags=["atlassian"])


# ================================================================
# Endpoints
# ================================================================


@router.get("/install")
async def install_atlassian():
    """
    Atlassian OAuth 설치 시작
    """
    atlassian_service = get_atlassian_oauth_client()
    state = secrets.token_urlsafe(32)

    await store_oauth_state(state, provider="atlassian")

    authorization_url = atlassian_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def atlassian_oauth_callback(
    code: str,
    background_tasks: BackgroundTasks,
    state: str | None = None,
    atlassian_service: AtlassianOAuthClient = Depends(get_atlassian_oauth_client),
):
    """
    Atlassian OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - 사용자 정보 + 접근 가능한 리소스 조회
    - 리소스별 토큰 저장
    - Jira 동기화/Webhook + Confluence 스텁 작업 등록
    """
    try:
        result = await _handle_atlassian_oauth_callback(
            provider="atlassian",
            code=code,
            background_tasks=background_tasks,
            state=state,
            atlassian_service=atlassian_service,
        )
    except CallbackError as exc:
        logger.warning(
            "atlassian_oauth_callback_failed",
            reason=exc.reason,
        )
        return RedirectResponse(
            url=_build_atlassian_failure_redirect_url(exc.reason)
        )
    except Exception:
        logger.error(
            "atlassian_oauth_callback_failed",
            reason="internal_error",
            exc_info=True,
        )
        return RedirectResponse(
            url=_build_atlassian_failure_redirect_url("internal_error")
        )

    return RedirectResponse(
        url=_build_atlassian_success_redirect_url(len(result.resources))
    )


@router.get("/status", response_model=AtlassianInstallationStatus)
async def atlassian_installation_status(
    atlassian_service: AtlassianOAuthClient = Depends(get_atlassian_oauth_client),
):
    """
    Atlassian 설치 상태 조회
    """
    cloud_id = await run_in_threadpool(_load_latest_cloud_id)
    if cloud_id is None:
        return AtlassianInstallationStatus(installed=False)

    try:
        token_manager = AtlassianTokenManager(
            oauth_client=atlassian_service,
            oauth_repository=atlassian_crud,
        )
        token_provider = AtlassianTokenProvider(token_manager)
        valid_token = await token_provider.get_access_token(cloud_id)
        resources = await atlassian_service.get_accessible_resources(valid_token)
        return AtlassianInstallationStatus(installed=True, resources=resources)
    except HTTPException as e:
        logger.warning(
            "atlassian_installation_status_failed",
            cloud_id=cloud_id,
            reason=e.detail,
        )
        return AtlassianInstallationStatus(installed=True, resources=[])
    except AtlassianError as e:
        logger.warning(
            "atlassian_installation_status_failed",
            cloud_id=cloud_id,
            reason=e.message,
        )
        return AtlassianInstallationStatus(installed=True, resources=[])
    except (HTTPStatusError, RequestError):
        logger.warning(
            "atlassian_installation_status_failed",
            cloud_id=cloud_id,
            reason="api_request_failed",
        )
        return AtlassianInstallationStatus(installed=True, resources=[])


@router.delete("/uninstall")
async def atlassian_uninstall(
    cloud_id: str = Query(..., description="삭제할 Atlassian Cloud ID"),
):
    """
    Atlassian 연결 해제
    """
    deleted = await run_in_threadpool(_delete_token_db, cloud_id)
    if deleted:
        return {"status": "success", "message": "Atlassian 연결이 해제되었습니다."}
    return {"status": "not_found", "message": "해당 Atlassian 연결을 찾을 수 없습니다."}


# =============================================================================
# Private Helper Functions
# =============================================================================
@audit_log(
    IntegrationAction.HANDLE_OAUTH_CALLBACK,
    metadata_factory=IntegrationAuditMetadata.from_audit,
    emit_attempt=True,
)
async def _handle_atlassian_oauth_callback(
    *,
    provider: str,
    code: str,
    background_tasks: BackgroundTasks,
    state: str | None,
    atlassian_service: AtlassianOAuthClient,
):
    callback_service = AtlassianCallbackService(atlassian_service)
    result = await callback_service.handle_callback(
        code=code,
        state=state,
    )

    await _register_atlassian_knowledge_sources(result)
    _schedule_atlassian_followups(background_tasks, result)
    return result


def _load_latest_cloud_id() -> str | None:
    with SessionLocal() as db:
        tokens = atlassian_crud.get_all_tokens(db)
        if not tokens:
            return None
        return tokens[0].cloud_id


def _delete_token_db(cloud_id: str) -> bool:
    with SessionLocal() as db:
        return atlassian_crud.delete_token(db, cloud_id)


async def _register_atlassian_knowledge_sources(result) -> None:
    for cloud_id in result.jira_targets:
        await _register_knowledge_source(cloud_id, SourceType.JIRA)

    for cloud_id in result.confluence_targets:
        await _register_knowledge_source(cloud_id, SourceType.CONFLUENCE)


def _schedule_atlassian_followups(
    background_tasks: BackgroundTasks,
    result,
) -> None:
    for cloud_id in result.jira_targets:
        background_tasks.add_task(_sync_jira_metadata, cloud_id)
        background_tasks.add_task(_ensure_jira_dynamic_webhook, cloud_id)

    for cloud_id in result.confluence_targets:
        background_tasks.add_task(_sync_confluence_metadata, cloud_id)


async def _register_knowledge_source(cloud_id: str, source_type: SourceType):
    def _register_knowledge_source_db():
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            
            if not workspace:
                logger.error(
                    "atlassian_knowledge_source_register_failed",
                    source_type=source_type.value,
                    reason="workspace_missing",
                    cloud_id=cloud_id,
                )
                return
            
            # 중복 등록 방지
            existing_source = db.scalar(
                select(KnowledgeSource).where(
                    (KnowledgeSource.workspace_id == workspace.id) &
                    (KnowledgeSource.source_type == source_type) &
                    (KnowledgeSource.external_identifier == cloud_id)
                )
            )
            
            if existing_source:
                logger.info(
                    "atlassian_knowledge_source_exists",
                    source_type=source_type.value,
                    cloud_id=cloud_id,
                )
                return
            
            name = "Jira" if source_type == SourceType.JIRA else "Confluence"
            new_source = KnowledgeSource(
                workspace_id=workspace.id,
                source_type=source_type,
                display_name=name,
                external_identifier=cloud_id    
            )
            add_knowledge_source(db, new_source)
            db.commit()
    await run_in_threadpool(_register_knowledge_source_db)


async def _sync_jira_metadata(cloud_id: str) -> None:
    """
    Jira 메타데이터 동기화 (BackgroundTask)
    """
    logger.info("jira_metadata_sync_started", cloud_id=cloud_id)

    try:
        service = await create_jira_ingestion_service(cloud_id=cloud_id)
        await service.sync_metadata()
        logger.info("jira_metadata_sync_completed", cloud_id=cloud_id)
    except Exception:
        logger.error(
            "jira_metadata_sync_failed",
            cloud_id=cloud_id,
            exc_info=True,
        )


async def _ensure_jira_dynamic_webhook(cloud_id: str) -> None:
    """
    Jira Dynamic Webhook 등록 보장 (BackgroundTask)
    """
    logger.info("jira_dynamic_webhook_ensure_started", cloud_id=cloud_id)

    try:
        dynamic_webhook_service = get_jira_dynamic_webhook_service()
        await dynamic_webhook_service.ensure_registered(cloud_id=cloud_id)
        logger.info("jira_dynamic_webhook_ensure_completed", cloud_id=cloud_id)
    except Exception:
        logger.error(
            "jira_dynamic_webhook_ensure_failed",
            cloud_id=cloud_id,
            exc_info=True,
        )


async def _sync_confluence_metadata(cloud_id: str) -> None:
    """Confluence Space 메타데이터 동기화 (BackgroundTask)."""
    logger.info("confluence_metadata_sync_started", cloud_id=cloud_id)

    try:
        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_crud,
        )
        service = ConfluenceMetadataService(token_manager)
        await service.sync_all(cloud_id)
        logger.info("confluence_metadata_sync_completed", cloud_id=cloud_id)
    except Exception:
        logger.error(
            "confluence_metadata_sync_failed",
            cloud_id=cloud_id,
            exc_info=True,
        )


def _build_atlassian_success_redirect_url(resource_count: int) -> str:
    return (
        f"{auth_settings.FRONTEND_REDIRECT_URI}"
        f"?atlassian_installed=true&count={resource_count}"
    )


def _build_atlassian_failure_redirect_url(reason: str) -> str:
    return (
        f"{auth_settings.FRONTEND_REDIRECT_URI}"
        f"?atlassian_installed=false&reason={reason}"
    )
