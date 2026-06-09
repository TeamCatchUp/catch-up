from __future__ import annotations

import secrets
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError
from httpx import RequestError
from sqlalchemy import select

from catchup.audit.actions import IntegrationAction
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.audit.utils import audit_log
from catchup.configs.config import auth_settings
from catchup.connectors.slack.auth import SlackOAuthService
from catchup.connectors.slack.auth import get_slack_oauth_service
from catchup.connectors.slack.schemas import SlackOAuthTokenResponse
from catchup.db.engine import SessionLocal
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import KnowledgeSource
from catchup.db.models import SourceType
from catchup.db.models import WorkflowCredentialVendor
from catchup.db.slack import oauth_repository as slack_crud
from catchup.db.workspaces import get_workspace_limit_one
from catchup.events.enums import EventType
from catchup.events.enums import IntegrationEventAction
from catchup.sync.metadata.registry import run_slack_metadata_sync
from catchup.utils.redis import consume_oauth_state_payload
from catchup.utils.redis import store_oauth_state
from catchup.workflow_credentials.oauth import build_oauth_completion_redirect
from catchup.workflow_credentials.oauth import consume_workflow_redirect_after
from catchup.workflow_credentials.oauth import split_oauth_scopes
from catchup.workflow_credentials.schemas import PersonalOAuthCredentialCreateRequest
from catchup.workflow_credentials.service import WorkflowCredentialAlreadyExists
from catchup.workflow_credentials.service import WorkflowCredentialService

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
        redirect_url = await _handle_slack_oauth_callback(
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
            url=_build_slack_failure_redirect_url(
                exc.reason,
                redirect_after=exc.redirect_after,
            )
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

    return RedirectResponse(url=redirect_url)


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
    def __init__(
        self,
        reason: str,
        redirect_after: str | None = None,
    ):
        self.reason = reason
        self.redirect_after = redirect_after
        super().__init__(reason)


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
) -> str:
    payload = await _validate_slack_callback_request(
        provider=provider,
        code=code,
        state=state,
        error=error,
    )

    purpose = payload["purpose"]
    try:
        tokens = await slack_service.exchange_code_for_tokens(code)
    except Exception as exc:
        if purpose == "workflow_personal":
            raise SlackCallbackError(
                "token_exchange_failed",
                redirect_after=payload.get("redirect_after"),
            ) from exc
        raise

    if purpose == "sync_install":
        await _persist_slack_installation(tokens)
        _schedule_slack_followups(background_tasks, tokens.team.id)
        return _build_slack_success_redirect_url(tokens.team.name)

    if purpose == "workflow_personal":
        try:
            await run_in_threadpool(_persist_slack_workflow_credential_db, tokens, payload)
        except SlackCallbackError:
            raise
        except Exception as exc:
            raise SlackCallbackError(
                "credential_persist_failed",
                redirect_after=payload.get("redirect_after"),
            ) from exc
        return build_oauth_completion_redirect(
            vendor="slack",
            success=True,
            redirect_after=payload.get("redirect_after"),
        )

    raise SlackCallbackError(
        "unsupported_purpose",
        redirect_after=payload.get("redirect_after"),
    )


async def _validate_slack_callback_request(
    *,
    provider: str,
    code: str | None,
    state: str | None,
    error: str | None,
) -> dict:
    failure_reason = error or ("no_code" if not code else None)
    if failure_reason:
        raise SlackCallbackError(
            failure_reason,
            redirect_after=await consume_workflow_redirect_after(
                provider=provider,
                state=state,
            ),
        )

    if not state:
        raise SlackCallbackError("missing_state")

    payload = await consume_oauth_state_payload(provider=provider, state=state)
    if payload is None:
        raise SlackCallbackError("invalid_state")

    return payload


async def _persist_slack_installation(tokens: SlackOAuthTokenResponse) -> None:
    await run_in_threadpool(
        _persist_slack_token_db,
        **_build_slack_token_payload(tokens),
    )
    await _register_knowledge_source(tokens.team.id)


def _schedule_slack_followups(
    background_tasks: BackgroundTasks,
    team_id: str,
) -> None:
    background_tasks.add_task(run_slack_metadata_sync, team_id)


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


def _build_slack_token_payload(tokens: SlackOAuthTokenResponse) -> dict[str, object]:
    if not tokens.access_token:
        raise SlackCallbackError("missing_bot_token")

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


def _persist_slack_workflow_credential_db(
    tokens: SlackOAuthTokenResponse,
    payload: dict,
) -> None:
    authed_user = tokens.authed_user
    if authed_user is None or not authed_user.access_token:
        raise SlackCallbackError(
            "missing_user_token",
            redirect_after=payload.get("redirect_after"),
        )

    with SessionLocal() as db:
        try:
            WorkflowCredentialService().create_personal_oauth(
                db,
                PersonalOAuthCredentialCreateRequest(
                    vendor=WorkflowCredentialVendor.SLACK,
                    workspace_id=int(payload["workspace_id"]),
                    user_id=int(payload["user_id"]),
                    display_name=tokens.team.name or "Slack",
                    external_tenant_id=tokens.team.id,
                    external_tenant_name=tokens.team.name,
                    external_account_id=authed_user.id,
                    external_account_name=None,
                    external_account_email=None,
                    server_url=None,
                    scopes=split_oauth_scopes(authed_user.scope),
                    token_payload={
                        "access_token": authed_user.access_token,
                        "refresh_token": authed_user.refresh_token,
                        "token_type": authed_user.token_type or "Bearer",
                    },
                    extra_metadata={
                        "app_id": tokens.app_id,
                        "team_id": tokens.team.id,
                    },
                    expires_in=authed_user.expires_in,
                ),
            )
        except WorkflowCredentialAlreadyExists as exc:
            raise SlackCallbackError(
                "already_connected",
                redirect_after=payload.get("redirect_after"),
            ) from exc


def _build_slack_success_redirect_url(team_name: str | None) -> str:
    return (
        f"{auth_settings.FRONTEND_REDIRECT_URI}"
        f"?slack_installed=true&team_name={team_name}"
    )


def _build_slack_failure_redirect_url(
    reason: str,
    redirect_after: str | None = None,
) -> str:
    if redirect_after:
        return build_oauth_completion_redirect(
            vendor="slack",
            success=False,
            redirect_after=redirect_after,
            reason=reason,
        )
    return (
        f"{auth_settings.FRONTEND_REDIRECT_URI}"
        f"?slack_installed=false&reason={reason}"
    )


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
