from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy import select

from catchup.audit.actions import IntegrationAction
from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.audit.utils import audit_log
from catchup.connectors.slack.auth import get_slack_oauth_service, SlackOAuthService
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.connectors.slack.schemas import (
    SlackInstallationStatus,
    SlackWorkspaceInfo,
)
from catchup.configs.config import auth_settings
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import KnowledgeSource, SourceType
from catchup.db.slack import oauth_repository as slack_crud
from catchup.db.workspaces import get_workspace_limit_one
from catchup.events.enums import EventType, IntegrationEventAction
from catchup.connectors.slack.factory import create_slack_metadata_service
from catchup.db.engine import SessionLocal
from catchup.utils.redis import store_oauth_state, validate_oauth_state


logger = structlog.get_logger()

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
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Slack OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - Workspace 정보 저장
    """
    try:
        result = await _handle_slack_oauth_callback(
            provider="slack",
            code=code,
            state=state,
            error=error,
            slack_service=slack_service,
            background_tasks=background_tasks,
        )
    except SlackCallbackError as exc:
        logger.warning(
            "slack_oauth_callback_failed",
            reason=exc.reason,
        )
        return RedirectResponse(
            url=_build_slack_failure_redirect_url(exc.reason)
        )
    except Exception:
        logger.error(
            "slack_oauth_callback_failed",
            reason="internal_error",
            exc_info=True,
        )
        return RedirectResponse(
            url=_build_slack_failure_redirect_url("internal_error")
        )

    return RedirectResponse(url=_build_slack_success_redirect_url(result.team_name))


@router.get("/status", response_model=SlackInstallationStatus)
async def slack_installation_status(
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """Slack 설치 상태 조회"""
    tokens = await run_in_threadpool(_load_all_slack_tokens_db)

    if not tokens:
        return SlackInstallationStatus(installed=False)

    workspaces = []
    for token in tokens:
        try:
            # 토큰 유효성 확인
            valid_token = await slack_service.get_valid_access_token(token)
            await slack_service.test_auth(valid_token)

            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=token.bot_scopes.split() if token.bot_scopes else [],
                connected_at=token.created_at,
            ))
        except (HTTPException, SlackRateLimitError) as e:
            detail = e.detail if isinstance(e, HTTPException) else e.message
            logger.warning(
                "slack_installation_status_failed",
                team_id=token.team_id,
                reason=detail,
            )
            # 토큰이 유효하지 않더라도 연결된 것으로 표시
            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=[],
                connected_at=token.created_at,
            ))
        except (HTTPStatusError, RequestError):
            logger.warning(
                "slack_installation_status_failed",
                team_id=token.team_id,
                reason="api_request_failed",
            )
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
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """Slack 연결 해제"""
    token = await run_in_threadpool(_load_slack_token_db, team_id)

    if not token:
        return {"status": "not_found", "message": "해당 Slack 연결을 찾을 수 없습니다."}

    if revoke_token:
        try:
            await slack_service.revoke_token(token.bot_access_token)
            logger.info("slack_token_revoked", team_id=team_id)
        except HTTPException as e:
            logger.warning(
                "slack_token_revocation_failed",
                team_id=team_id,
                reason=e.detail,
            )
        except (HTTPStatusError, RequestError):
            logger.warning(
                "slack_token_revocation_failed",
                team_id=team_id,
                reason="api_request_failed",
            )

    deleted = await run_in_threadpool(_delete_slack_token_db, team_id)
    if deleted:
        return {"status": "success", "message": "Slack 연결이 해제되었습니다."}

    return {"status": "error", "message": "연결 해제 중 오류가 발생했습니다."}


# =============================================================================
# Private Helper Functions
# =============================================================================
class SlackCallbackError(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        self.reason = reason
        self.detail = detail
        super().__init__(detail or reason)


@dataclass(slots=True, frozen=True)
class SlackCallbackResult:
    team_id: str
    team_name: str | None


@audit_log(
    IntegrationAction.HANDLE_OAUTH_CALLBACK,
    metadata_factory=IntegrationAuditMetadata.from_audit,
    emit_attempt=True,
)
async def _handle_slack_oauth_callback(
    *,
    provider: str,
    code: str | None,
    state: str | None,
    error: str | None,
    slack_service: SlackOAuthService,
    background_tasks: BackgroundTasks,
) -> SlackCallbackResult:
    await _validate_slack_callback_request(
        provider=provider,
        code=code,
        state=state,
        error=error,
    )

    tokens = await slack_service.exchange_code_for_tokens(code)
    await _persist_slack_installation(tokens)
    _schedule_slack_followups(background_tasks, tokens.team.id)
    return SlackCallbackResult(
        team_id=tokens.team.id,
        team_name=tokens.team.name,
    )


async def _validate_slack_callback_request(
    *,
    provider: str,
    code: str | None,
    state: str | None,
    error: str | None,
) -> None:
    if error:
        raise SlackCallbackError(error)

    if not code:
        raise SlackCallbackError("no_code")

    if not state:
        raise SlackCallbackError("missing_state")

    is_valid_state = await validate_oauth_state(state, provider=provider)
    if not is_valid_state:
        raise SlackCallbackError("invalid_state")


async def _persist_slack_installation(tokens) -> None:
    await run_in_threadpool(
        _persist_slack_token_db,
        **_build_slack_token_payload(tokens),
    )
    await _register_knowledge_source(tokens.team.id)


def _schedule_slack_followups(
    background_tasks: BackgroundTasks,
    team_id: str,
) -> None:
    background_tasks.add_task(_refresh_workspace_metadata, team_id)


async def _register_knowledge_source(team_id: str):
    def _sync_task():
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            
            if not workspace:
                logger.error(
                    "slack_knowledge_source_register_failed",
                    reason="workspace_missing",
                    team_id=team_id,
                )
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
                logger.info(
                    "slack_knowledge_source_exists",
                    team_id=team_id,
                )
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


async def _refresh_workspace_metadata(team_id: str) -> None:
    """
    OAuth 설치 직후 메타데이터 동기화 (BackgroundTask)

    독립 DB 세션으로 Workspace, Users, Channels, Channel Members 수집.
    """
    logger.info("slack_metadata_sync_started", team_id=team_id)

    try:
        service = await create_slack_metadata_service(team_id)
        await service.sync_metadata()
        logger.info("slack_metadata_sync_completed", team_id=team_id)
    except Exception:
        logger.error(
            "slack_metadata_sync_failed",
            team_id=team_id,
            exc_info=True,
        )


def _persist_slack_token_db(
    *,
    team_id: str,
    team_name: str | None,
    bot_user_id: str,
    bot_access_token: str,
    bot_scopes: str,
    authed_user_id: str | None = None,
    bot_refresh_token: str | None = None,
    bot_token_expires_at: datetime | None = None,
    incoming_webhook_url: str | None = None,
    incoming_webhook_channel: str | None = None,
):
    with SessionLocal() as db:
        try:
            slack_crud.create_or_update_slack_token(
                db=db,
                team_id=team_id,
                team_name=team_name,
                bot_user_id=bot_user_id,
                bot_access_token=bot_access_token,
                bot_scopes=bot_scopes,
                authed_user_id=authed_user_id,
                bot_refresh_token=bot_refresh_token,
                bot_token_expires_at=bot_token_expires_at,
                incoming_webhook_url=incoming_webhook_url,
                incoming_webhook_channel=incoming_webhook_channel,
            )
            db.commit()
            emit_audit_event(
                event_type=EventType.INTEGRATION,
                event_action=IntegrationEventAction.OAUTH_TOKEN_PERSISTED,
                event_status=AuditEventStatus.SUCCESS,
                level=AuditLevel.INFO,
                metadata=IntegrationAuditMetadata(
                    context=f"slack_oauth_token_persisted:team_id={team_id}",
                    provider="slack",
                ),
                immediate=True,
            )
        except Exception:
            db.rollback()
            raise


def _build_slack_token_payload(tokens) -> dict:
    bot_expires_at = None
    if tokens.expires_in:
        bot_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

    return {
        "team_id": tokens.team.id,
        "team_name": tokens.team.name,
        "bot_user_id": tokens.bot_user_id,
        "bot_access_token": tokens.access_token,
        "bot_scopes": tokens.scope,
        "authed_user_id": tokens.authed_user.id if tokens.authed_user else None,
        "bot_refresh_token": tokens.refresh_token,
        "bot_token_expires_at": bot_expires_at,
        "incoming_webhook_url": tokens.incoming_webhook.url if tokens.incoming_webhook else None,
        "incoming_webhook_channel": tokens.incoming_webhook.channel if tokens.incoming_webhook else None,
    }


def _build_slack_success_redirect_url(team_name: str | None) -> str:
    return (
        f"{auth_settings.FRONTEND_REDIRECT_URI}"
        f"?slack_installed=true&team_name={team_name}"
    )


def _build_slack_failure_redirect_url(reason: str) -> str:
    return (
        f"{auth_settings.FRONTEND_REDIRECT_URI}"
        f"?slack_installed=false&reason={reason}"
    )


def _load_all_slack_tokens_db():
    with SessionLocal() as db:
        return slack_crud.get_all_slack_tokens(db)


def _load_slack_token_db(team_id: str):
    with SessionLocal() as db:
        return slack_crud.get_slack_token_by_team_id(db, team_id)


def _delete_slack_token_db(team_id: str) -> bool:
    with SessionLocal() as db:
        try:
            deleted = slack_crud.delete_slack_token(db, team_id)
            db.commit()
            return deleted
        except Exception:
            db.rollback()
            raise
