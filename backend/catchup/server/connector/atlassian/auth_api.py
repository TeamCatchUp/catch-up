"""
Atlassian Auth API

Atlassian OAuth 통합 인증 API 엔드포인트.
하나의 OAuth 앱으로 Jira + Confluence 접근 권한을 획득한다.
"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from catchup.audit.actions import IntegrationAction
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.utils import audit_log
from catchup.configs.config import auth_settings
from catchup.connectors.atlassian.callback_service import AtlassianCallbackService
from catchup.connectors.atlassian.callback_service import CallbackError
from catchup.connectors.atlassian.callback_service import CallbackResult
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.oauth_client import get_atlassian_oauth_client
from catchup.connectors.jira.dynamic_webhook_service import (
    get_jira_dynamic_webhook_service,
)
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.db.engine import SessionLocal
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import KnowledgeSource
from catchup.db.models import SourceType
from catchup.db.models import WorkflowCredentialVendor
from catchup.db.workspaces import get_workspace_limit_one
from catchup.sync.metadata.registry import run_confluence_metadata_sync
from catchup.sync.metadata.registry import run_jira_metadata_sync
from catchup.utils.redis import consume_oauth_state_payload
from catchup.utils.redis import store_oauth_state
from catchup.workflow_credentials.oauth import build_oauth_completion_redirect
from catchup.workflow_credentials.oauth import consume_workflow_redirect_after
from catchup.workflow_credentials.schemas import PersonalOAuthCredentialCreateRequest
from catchup.workflow_credentials.service import WorkflowCredentialAlreadyExists
from catchup.workflow_credentials.service import WorkflowCredentialService

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
    background_tasks: BackgroundTasks,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
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
        redirect_url = await _handle_atlassian_oauth_callback(
            provider="atlassian",
            code=code,
            background_tasks=background_tasks,
            state=state,
            error=error,
            atlassian_service=atlassian_service,
        )
    except CallbackError as exc:
        logger.warning(
            "atlassian_oauth_callback_failed",
            reason=exc.reason,
        )
        redirect_after = getattr(exc, "redirect_after", None)
        if redirect_after:
            return RedirectResponse(
                url=build_oauth_completion_redirect(
                    vendor="atlassian",
                    success=False,
                    redirect_after=redirect_after,
                    reason=exc.reason,
                )
            )
        return RedirectResponse(url=_build_atlassian_failure_redirect_url(exc.reason))
    except Exception:
        logger.error(
            "atlassian_oauth_callback_failed",
            reason="internal_error",
            exc_info=True,
        )
        return RedirectResponse(
            url=_build_atlassian_failure_redirect_url("internal_error")
        )

    return RedirectResponse(url=redirect_url)


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
class AtlassianWorkflowCallbackError(CallbackError):
    def __init__(self, reason: str, redirect_after: str | None):
        self.redirect_after = redirect_after
        super().__init__(reason)


@audit_log(
    IntegrationAction.HANDLE_OAUTH_CALLBACK,
    metadata_factory=IntegrationAuditMetadata.from_audit,
    emit_attempt=True,
)
async def _handle_atlassian_oauth_callback(
    *,
    provider: str,
    code: str | None,
    background_tasks: BackgroundTasks,
    state: str | None,
    error: str | None,
    atlassian_service: AtlassianOAuthClient,
) -> str:
    failure_reason = error or ("no_code" if not code else None)
    if failure_reason:
        redirect_after = await consume_workflow_redirect_after(
            provider=provider,
            state=state,
        )
        if redirect_after:
            raise AtlassianWorkflowCallbackError(failure_reason, redirect_after)
        raise CallbackError(failure_reason)

    if state is None:
        raise CallbackError("invalid_state")

    payload = await consume_oauth_state_payload(provider=provider, state=state)
    if payload is None:
        raise CallbackError("invalid_state")

    callback_service = AtlassianCallbackService(atlassian_service)
    try:
        context = await callback_service.collect_oauth_context(code=code)
    except Exception as exc:
        if payload["purpose"] == "workflow_personal":
            raise AtlassianWorkflowCallbackError(
                "token_exchange_failed",
                payload.get("redirect_after"),
            ) from exc
        raise

    if payload["purpose"] == "sync_install":
        result = await callback_service.persist_sync_context(context)
        await _register_atlassian_knowledge_sources(result)
        _schedule_atlassian_followups(background_tasks, result)
        return _build_atlassian_success_redirect_url(len(result.resources))

    if payload["purpose"] == "workflow_personal":
        try:
            await run_in_threadpool(_persist_atlassian_workflow_credentials_db, context, payload)
        except WorkflowCredentialAlreadyExists as exc:
            raise AtlassianWorkflowCallbackError(
                "already_connected",
                payload.get("redirect_after"),
            ) from exc
        except Exception as exc:
            raise AtlassianWorkflowCallbackError(
                "credential_persist_failed",
                payload.get("redirect_after"),
            ) from exc
        return build_oauth_completion_redirect(
            vendor="atlassian",
            success=True,
            redirect_after=payload.get("redirect_after"),
        )

    raise CallbackError("unsupported_purpose")


def _persist_atlassian_workflow_credentials_db(context, payload: dict) -> None:
    with SessionLocal() as db:
        WorkflowCredentialService().create_personal_oauth(
            db,
            _build_atlassian_personal_oauth_request(context, payload),
        )


def _build_atlassian_personal_oauth_request(
    context,
    payload: dict,
) -> PersonalOAuthCredentialCreateRequest:
    resources = [_build_atlassian_resource_metadata(context, resource) for resource in context.resources]
    scopes = sorted({scope for resource in resources for scope in resource["scopes"]})
    account_name = context.user_info.name or context.user_info.email or context.user_info.account_id
    return PersonalOAuthCredentialCreateRequest(
        vendor=WorkflowCredentialVendor.ATLASSIAN,
        workspace_id=int(payload["workspace_id"]),
        user_id=int(payload["user_id"]),
        display_name=f"Atlassian ({account_name})",
        external_tenant_id="atlassian",
        external_tenant_name="Atlassian",
        external_account_id=context.user_info.account_id,
        external_account_name=context.user_info.name,
        external_account_email=context.user_info.email,
        server_url=None,
        scopes=scopes,
        token_payload={
            "access_token": context.tokens.access_token,
            "refresh_token": context.tokens.refresh_token,
            "token_type": context.tokens.token_type,
            "resources": resources,
        },
        extra_metadata={
            "resources": resources,
        },
        expires_in=context.tokens.expires_in,
    )


def _build_atlassian_resource_metadata(context, resource) -> dict:
    return {
        "id": resource.id,
        "name": resource.name,
        "url": resource.url,
        "avatar_url": resource.avatar_url,
        "scopes": sorted(context.aggregated_scopes.get(resource.id, set())),
    }


def _delete_token_db(cloud_id: str) -> bool:
    with SessionLocal() as db:
        return atlassian_crud.delete_token(db, cloud_id)


async def _register_atlassian_knowledge_sources(result: CallbackResult) -> None:
    for cloud_id in result.jira_targets:
        await _register_knowledge_source(cloud_id, SourceType.JIRA)

    for cloud_id in result.confluence_targets:
        await _register_knowledge_source(cloud_id, SourceType.CONFLUENCE)


def _schedule_atlassian_followups(
    background_tasks: BackgroundTasks,
    result: CallbackResult,
) -> None:
    for cloud_id in result.jira_targets:
        background_tasks.add_task(run_jira_metadata_sync, cloud_id)
        background_tasks.add_task(_ensure_jira_dynamic_webhook, cloud_id)

    for cloud_id in result.confluence_targets:
        background_tasks.add_task(run_confluence_metadata_sync, cloud_id)


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


async def _ensure_jira_dynamic_webhook(cloud_id: str) -> None:
    """
    Jira Dynamic Webhook 등록 보장 (BackgroundTask)
    """
    logger.info("jira_dynamic_webhook_ensure_started", cloud_id=cloud_id)

    try:
        dynamic_webhook_service = get_jira_dynamic_webhook_service()
        await dynamic_webhook_service.ensure_registered(
            cloud_id=cloud_id,
            source="initial_install",
        )
        logger.info("jira_dynamic_webhook_ensure_completed", cloud_id=cloud_id)
    except Exception:
        logger.error(
            "jira_dynamic_webhook_ensure_failed",
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
