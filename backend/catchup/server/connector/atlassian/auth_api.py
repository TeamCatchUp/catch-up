"""
Atlassian Auth API

Atlassian OAuth 통합 인증 API 엔드포인트.
하나의 OAuth 앱으로 Jira + Confluence 접근 권한을 획득한다.
"""

import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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
        background_tasks.add_task(_sync_jira_metadata, cloud_id)
        background_tasks.add_task(_ensure_jira_dynamic_webhook, cloud_id)

    for cloud_id in result.confluence_targets:
        background_tasks.add_task(_sync_confluence_metadata, cloud_id)
        background_tasks.add_task(_ensure_confluence_webhook, cloud_id)

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



async def _ensure_confluence_webhook(cloud_id: str) -> None:
    """
    Confluence Webhook 등록 보장 (BackgroundTask)

    TODO: Phase 3에서 Confluence webhook 등록/갱신으로 확장
    (현재 스텁 로그만 남기며, 추후 이벤트 동기화 정책 정합성 점검 필요).
    """
    logger.info(
        f"[ATLASSIAN][AUTH] Confluence webhook ensure skipped (Phase 3): "
        f"cloud_id={cloud_id}"
    )
