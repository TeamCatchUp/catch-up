import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.connectors.slack.auth import get_slack_oauth_service, SlackOAuthService
from catchup.connectors.slack.schemas import (
    SlackInstallationStatus,
    SlackWorkspaceInfo,
)
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import KnowledgeSource, SourceType
from catchup.db.slack import oauth_repository as slack_crud
from catchup.db.workspaces import get_workspace_limit_one
from catchup.events.enums import EventType, IntegrationEventAction
from catchup.utils.redis import store_oauth_state, validate_oauth_state
from catchup.connectors.slack.factory import create_slack_metadata_service
from catchup.db.engine import SessionLocal


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/slack", tags=["slack"])


@router.get("/install")
async def install_slack():
    slack_service = get_slack_oauth_service()
    state = secrets.token_urlsafe(32)

    await store_oauth_state(state, provider="slack")

    authorization_url = slack_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def slack_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Slack OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - Workspace 정보 저장
    """
    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.OAUTH_CALLBACK,
        event_status=AuditEventStatus.ATTEMPT,
        level=AuditLevel.INFO,
        metadata=IntegrationAuditMetadata(
            context="slack_oauth_callback",
            provider="slack",
        ),
        immediate=True,
    )

    # 에러 처리 (사용자가 취소한 경우)
    if error:
        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.OAUTH_CALLBACK,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.WARNING,
            metadata=IntegrationAuditMetadata(
                context=f"slack_oauth_callback:{error}",
                provider="slack",
            ),
            immediate=True,
        )
        logger.warning(f"[SLACK][AUTH] OAuth error: {error}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason={error}"
        )

    if not code:
        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.OAUTH_CALLBACK,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.WARNING,
            metadata=IntegrationAuditMetadata(
                context="slack_oauth_callback:no_code",
                provider="slack",
            ),
            immediate=True,
        )
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason=no_code"
        )

    # State 파라미터 검증 (CSRF 방지)
    if not state:
        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.OAUTH_CALLBACK,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.WARNING,
            metadata=IntegrationAuditMetadata(
                context="slack_oauth_callback:missing_state",
                provider="slack",
            ),
            immediate=True,
        )
        logger.warning("[SLACK][AUTH] Missing OAuth state parameter")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason=missing_state"
        )

    is_valid_state = await validate_oauth_state(state, provider="slack")
    if not is_valid_state:
        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.OAUTH_CALLBACK,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.WARNING,
            metadata=IntegrationAuditMetadata(
                context="slack_oauth_callback:invalid_state",
                provider="slack",
            ),
            immediate=True,
        )
        logger.warning(f"[SLACK][AUTH] OAuth state validation failed: {state}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason=invalid_state"
        )

    # 1. Code → Token 교환
    tokens = await slack_service.exchange_code_for_tokens(code)

    # 2. Token Rotation 사용 시 만료 시간 계산
    bot_expires_at = None
    if tokens.expires_in:
        bot_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

    # 3. Token 저장
    slack_crud.create_or_update_slack_token(
        db=db,
        team_id=tokens.team.id,
        team_name=tokens.team.name,
        bot_user_id=tokens.bot_user_id,
        bot_access_token=tokens.access_token,
        bot_scopes=tokens.scope,
        authed_user_id=tokens.authed_user.id if tokens.authed_user else None,
        bot_refresh_token=tokens.refresh_token,
        bot_token_expires_at=bot_expires_at,
        incoming_webhook_url=tokens.incoming_webhook.url if tokens.incoming_webhook else None,
        incoming_webhook_channel=tokens.incoming_webhook.channel if tokens.incoming_webhook else None,
    )

    logger.info(f"[SLACK][AUTH] Installation completed: team_id={tokens.team.id}, name={tokens.team.name}")
    
    # Knowleged Source 등록
    await _register_knowledge_source(tokens.team.id)
    
    # 4. 메타데이터 동기화 (BackgroundTask)
    background_tasks.add_task(_sync_workspace_metadata, tokens.team.id)

    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.OAUTH_CALLBACK,
        event_status=AuditEventStatus.SUCCESS,
        level=AuditLevel.INFO,
        metadata=IntegrationAuditMetadata(
            context="slack_oauth_callback:success",
            provider="slack",
        ),
        immediate=True,
    )

    # 5. 프론트엔드로 리다이렉트
    return RedirectResponse(
        url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=true&team_name={tokens.team.name}"
    )


@router.get("/status", response_model=SlackInstallationStatus)
async def slack_installation_status(
    db: Session = Depends(get_db),
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """Slack 설치 상태 조회"""
    tokens = slack_crud.get_all_slack_tokens(db)

    if not tokens:
        return SlackInstallationStatus(installed=False)

    workspaces = []
    for token in tokens:
        try:
            # 토큰 유효성 확인
            valid_token = await slack_service.get_valid_access_token(db, token)
            await slack_service.test_auth(valid_token)

            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=token.bot_scopes.split() if token.bot_scopes else [],
                connected_at=token.created_at,
            ))
        except HTTPException as e:
            logger.warning(f"[SLACK][AUTH] Status check failed (team={token.team_id}): {e.detail}")
            # 토큰이 유효하지 않더라도 연결된 것으로 표시
            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=[],
                connected_at=token.created_at,
            ))
        except (HTTPStatusError, RequestError) as e:
            logger.warning(f"[SLACK][AUTH] API request failed (team={token.team_id}): {e}")
            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=[],
                connected_at=token.created_at,
            ))

    return SlackInstallationStatus(installed=True, workspaces=workspaces)


@router.delete("/uninstall")
async def slack_uninstall(
    team_id: str = Query(..., description="삭제할 Slack Team ID"),
    revoke_token: bool = Query(default=True, description="Token 취소 여부"),
    db: Session = Depends(get_db),
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """Slack 연결 해제"""
    token = slack_crud.get_slack_token_by_team_id(db, team_id)

    if not token:
        return {"status": "not_found", "message": "해당 Slack 연결을 찾을 수 없습니다."}

    if revoke_token:
        try:
            await slack_service.revoke_token(token.bot_access_token)
            logger.info(f"[SLACK][AUTH] Token revoked: team_id={team_id}")
        except HTTPException as e:
            logger.warning(f"[SLACK][AUTH] Token revocation failed: {e.detail}")
        except (HTTPStatusError, RequestError) as e:
            logger.warning(f"[SLACK][AUTH] Token revocation API failed: {e}")

    deleted = slack_crud.delete_slack_token(db, team_id)
    if deleted:
        return {"status": "success", "message": "Slack 연결이 해제되었습니다."}

    return {"status": "error", "message": "연결 해제 중 오류가 발생했습니다."}


# =============================================================================
# Private Helper Functions
# =============================================================================
async def _register_knowledge_source(team_id: str):
    def _sync_task():
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            
            if not workspace:
                logger.error("[SLACK] 등록된 워크스페이스가 없습니다. 관리자에게 문의하세요.")
                return
            
            # 중복 등록 방지
            existing_source = db.scalar(
                select(KnowledgeSource).where(
                    (KnowledgeSource.workspace_id == workspace.id) &
                    (KnowledgeSource.source_type == SourceType.SLACK) &
                    (KnowledgeSource.external_identifier == team_id)
                )
            )
            
            if existing_source:
                logger.info(f"[SLACK] 이미 등록된 지식 소스입니다. (team_id={team_id})")
                return
            
            new_source = KnowledgeSource(
                workspace_id=workspace.id,
                source_type=SourceType.SLACK,
                display_name="Slack",
                external_identifier=team_id    
            )
            add_knowledge_source(db, new_source)
            db.commit()
    await run_in_threadpool(_sync_task)


async def _sync_workspace_metadata(team_id: str) -> None:
    """
    OAuth 설치 직후 메타데이터 동기화 (BackgroundTask)

    독립 DB 세션으로 Workspace, Users, Channels, Channel Members 수집.
    """
    logger.info(f"[SLACK][AUTH] Starting background metadata sync: team_id={team_id}")

    db = SessionLocal()
    try:
        service = await create_slack_metadata_service(db, team_id)
        results = await service.sync_metadata(db)
        logger.info(f"[SLACK][AUTH] Background metadata sync completed: team_id={team_id}, results={results}")
    except Exception as e:
        logger.error(f"[SLACK][AUTH] Background metadata sync failed: team_id={team_id}, error={e}")
    finally:
        db.close()
