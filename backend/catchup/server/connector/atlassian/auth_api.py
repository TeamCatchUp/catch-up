"""
Atlassian Auth API

Atlassian OAuth 통합 인증 API 엔드포인트.
하나의 OAuth 앱으로 Jira + Confluence 접근 권한을 획득한다.
"""

import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.oauth_client import (
    AtlassianOAuthClient,
    AtlassianOAuthService,
    get_atlassian_oauth_service,
)
from catchup.connectors.atlassian.callback_service import (
    AtlassianCallbackService,
    CallbackError,
)
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.confluence.metadata_service import ConfluenceMetadataService
from catchup.connectors.atlassian.schemas import AtlassianInstallationStatus
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.jira.dynamic_webhook_service import (
    get_jira_dynamic_webhook_service,
)
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import KnowledgeSource, SourceType
from catchup.db.user_source_mapping import upsert_okta_users
from catchup.mapping.okta import OktaClient
from catchup.mapping.resolver import sync_users_to_pre_mapping_buffer
from catchup.utils.redis import store_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/atlassian", tags=["atlassian"])


# ================================================================
# Endpoints
# ================================================================


@router.get("/install")
async def install_atlassian():
    """
    Atlassian OAuth 설치 시작
    """
    atlassian_service = get_atlassian_oauth_service()
    state = secrets.token_urlsafe(32)

    await store_oauth_state(state, provider="atlassian")

    authorization_url = atlassian_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def atlassian_oauth_callback(
    code: str,
    background_tasks: BackgroundTasks,
    state: str | None = None,
    db: Session = Depends(get_db),
    atlassian_service: AtlassianOAuthService = Depends(get_atlassian_oauth_service),
):
    """
    Atlassian OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - 사용자 정보 + 접근 가능한 리소스 조회
    - 리소스별 토큰 저장
    - Jira 동기화/Webhook + Confluence 스텁 작업 등록
    """
    callback_service = AtlassianCallbackService(atlassian_service)

    try:
        result = await callback_service.handle_callback(
            db=db,
            code=code,
            state=state,
        )
    except CallbackError as e:
        logger.warning(f"[ATLASSIAN][AUTH] Callback failed: code={e.code}, detail={e.detail}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=false&reason={e.code}"
        )
    except Exception as e:
        logger.error(f"[ATLASSIAN][AUTH] Callback unexpected error: {e}", exc_info=True)
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=false&reason=internal_error"
        )
    

    # Background tasks
    for cloud_id in result.jira_targets:
        await _register_knowledge_source(cloud_id, SourceType.JIRA)
        background_tasks.add_task(_sync_jira_metadata, cloud_id)
        background_tasks.add_task(_ensure_jira_dynamic_webhook, cloud_id)

    for cloud_id in result.confluence_targets:
        await _register_knowledge_source(cloud_id, SourceType.CONFLUENCE)
        background_tasks.add_task(_sync_confluence_metadata, cloud_id)
        background_tasks.add_task(_ensure_confluence_webhook, cloud_id)
        
    if result.jira_targets or result.confluence_targets:
        background_tasks.add_task(_sync_okta_users_and_map_all_sources)

    logger.info(
        f"[ATLASSIAN][AUTH] 설치 완료: {len(result.resources)}개 사이트 연결 (Jira + Confluence)"
    )

    return RedirectResponse(
        url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=true&count={len(result.resources)}"
    )


@router.get("/status", response_model=AtlassianInstallationStatus)
async def atlassian_installation_status(
    db: Session = Depends(get_db),
    atlassian_service: AtlassianOAuthService = Depends(get_atlassian_oauth_service),
):
    """
    Atlassian 설치 상태 조회
    """
    tokens = atlassian_crud.get_all_tokens(db)

    if not tokens:
        return AtlassianInstallationStatus(installed=False)

    try:
        valid_token = await atlassian_service.get_valid_access_token(db, tokens[0])
        resources = await atlassian_service.get_accessible_resources(valid_token)
        return AtlassianInstallationStatus(installed=True, resources=resources)
    except HTTPException as e:
        logger.warning(f"[ATLASSIAN][AUTH] 상태 조회 실패: {e.detail}")
        return AtlassianInstallationStatus(installed=True, resources=[])
    except (HTTPStatusError, RequestError) as e:
        logger.warning(f"[ATLASSIAN][AUTH] API 요청 실패: {e}")
        return AtlassianInstallationStatus(installed=True, resources=[])


@router.delete("/uninstall")
async def atlassian_uninstall(
    cloud_id: str = Query(..., description="삭제할 Atlassian Cloud ID"),
    db: Session = Depends(get_db),
):
    """
    Atlassian 연결 해제
    """
    deleted = atlassian_crud.delete_token(db, cloud_id)
    if deleted:
        return {"status": "success", "message": "Atlassian 연결이 해제되었습니다."}
    return {"status": "not_found", "message": "해당 Atlassian 연결을 찾을 수 없습니다."}


# =============================================================================
# Private Helper Functions
# =============================================================================
async def _register_knowledge_source(cloud_id: str, source_type: SourceType):
    def _sync_task():
        with SessionLocal() as db:
            name = "Jira" if source_type == SourceType.JIRA else "Confluence"
            new_source = KnowledgeSource(
                workspace_id=1,
                source_type=source_type,
                display_name=name,
                external_identifier=cloud_id    
            )
            add_knowledge_source(db, new_source)
            db.commit()
    await run_in_threadpool(_sync_task)


async def _sync_okta_users_and_map_all_sources() -> None:
    """Atlassian 메타데이터 fetching 이후 사용자 매핑까지 수행하는 Wrapper 함수 (임시)"""
    
    logger.info("[MAPPING] Starting integrated Okta sync and multi-source mapping")
    
    # Okta Users 기반 Atlassian Users 매핑
    try:
        okta_client = OktaClient()
        okta_users = await okta_client.get_parsed_users()
        
        if not okta_users:
            logger.warning("[MAPPING] No active users found in Okta. Skipping.")
            return
        
        def _mapping_task_sync():
            with SessionLocal() as db:
                try:
                    upsert_okta_users(db, okta_users)
                    
                    sources_to_map = [SourceType.JIRA, SourceType.CONFLUENCE]
                    results = {}
                    for source_type in sources_to_map:
                        results[source_type.value] = sync_users_to_pre_mapping_buffer(
                            db=db,
                            source_type=source_type,
                            okta_users=okta_users
                        )
                    db.commit()
                    return results
                    
                except Exception as e:
                    db.rollback() 
                    logger.error(f"Transaction failed, rolling back: {e}")
                    raise
            
        combined_mapping_result = await run_in_threadpool(_mapping_task_sync)
        logger.info(f"[OKTA][MAPPING] Mapping completed: {combined_mapping_result}")
            
    except Exception as e:
        logger.error(f"[MAPPING] Integrated mapping failed: {e}", exc_info=True)


async def _sync_jira_metadata(cloud_id: str) -> None:
    """
    Jira 메타데이터 동기화 (BackgroundTask)
    """
    logger.info(
        f"[ATLASSIAN][AUTH] Starting background metadata sync: cloud_id={cloud_id}"
    )

    db = SessionLocal()
    try:
        service = await create_jira_ingestion_service(db, cloud_id)
        results = await service.sync_metadata(db)
        logger.info(
            f"[ATLASSIAN][AUTH] Background metadata sync completed: "
            f"cloud_id={cloud_id}, results={results}"
        )
    except Exception as e:
        logger.error(
            f"[ATLASSIAN][AUTH] Background metadata sync failed: "
            f"cloud_id={cloud_id}, error={e}"
        )
    finally:
        db.close()


async def _ensure_jira_dynamic_webhook(cloud_id: str) -> None:
    """
    Jira Dynamic Webhook 등록 보장 (BackgroundTask)
    """
    logger.info(
        f"[ATLASSIAN][AUTH] Ensuring Jira dynamic webhook: cloud_id={cloud_id}"
    )

    db = SessionLocal()
    try:
        dynamic_webhook_service = get_jira_dynamic_webhook_service()
        result = await dynamic_webhook_service.ensure_registered(
            db=db, cloud_id=cloud_id
        )
        logger.info(
            f"[ATLASSIAN][AUTH] Jira dynamic webhook ensured: "
            f"cloud_id={cloud_id}, result={result}"
        )
    except Exception as e:
        logger.error(
            f"[ATLASSIAN][AUTH] Jira dynamic webhook ensure failed: "
            f"cloud_id={cloud_id}, error={e}",
            exc_info=True,
        )
    finally:
        db.close()


async def _sync_confluence_metadata(cloud_id: str) -> None:
    """Confluence Space 메타데이터 동기화 (BackgroundTask)."""
    logger.info(f"[CONFLUENCE][METADATA] Starting Space Sync : cloud_id={cloud_id}")

    db = SessionLocal()
    try:
        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_crud,
        )
        service = ConfluenceMetadataService(token_manager)
        result = await service.sync_all(db, cloud_id)
        logger.info(
            f"[CONFLUENCE][METADATA] Completed sync: cloud_id={cloud_id}, result={result}"
        )
    except Exception as e:
        logger.error(
            f"[CONFLUENCE][METADATA] Sync failed: cloud_id={cloud_id}, error={e}",
            exc_info=True,
        )
    finally:
        db.close()
