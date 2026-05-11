import logging
from typing import Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from catchup.configs.config import auth_settings
from catchup.connectors.github.auth import GitHubUserOAuthService
from catchup.connectors.github.auth import get_github_user_oauth_service
from catchup.db.engine import SessionLocal
from catchup.db.github import installation_repository as installation_crud
from catchup.db.models import WorkflowCredentialVendor
from catchup.utils.redis import consume_oauth_state_payload
from catchup.workflow_credentials.oauth import build_oauth_completion_redirect
from catchup.workflow_credentials.oauth import consume_workflow_redirect_after
from catchup.workflow_credentials.oauth import split_oauth_scopes
from catchup.workflow_credentials.schemas import PersonalOAuthCredentialCreateRequest
from catchup.workflow_credentials.service import WorkflowCredentialAlreadyExists
from catchup.workflow_credentials.service import WorkflowCredentialService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["GitHub Connector"])


def _load_installation_account(installation_id: int) -> str | None:
    with SessionLocal() as db:
        installation = installation_crud.get_installation_by_installation_id(
            db,
            installation_id,
        )
        if installation is None:
            return None
        return installation.account_login


@router.get("/install")
async def github_app_install_callback(
    installation_id: Optional[int] = Query(None),
    setup_action: Optional[str] = Query(None),
):
    """
    GitHub App 설치 완료 후 Callback 엔드포인트

    GitHub App 설정에서 "Setup URL (optional)"로 등록:
    https://your-domain.com/api/v1/github/install

    GitHub이 전달하는 Query Parameters:
    - installation_id: 설치된 Installation ID
    - setup_action: "install" (신규 설치) 또는 "update" (권한 변경)
    """
    logger.info(
        f"GitHub App install callback received: "
        f"installation_id={installation_id}, setup_action={setup_action}"
    )

    if not installation_id:
        logger.warning("GitHub App install callback received without installation_id")
        redirect_url = f"{auth_settings.FRONTEND_REDIRECT_URI}?github_install=error&reason=missing_installation_id"
        return RedirectResponse(url=redirect_url)

    account_login = await run_in_threadpool(
        _load_installation_account,
        installation_id,
    )

    if account_login:
        logger.info(
            f"GitHub App installation found: "
            f"installation_id={installation_id}, account={account_login}"
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=success"
            f"&installation_id={installation_id}"
            f"&account={account_login}"
        )
    else:
        logger.info(
            f"GitHub App installation not yet in DB: installation_id={installation_id}. "
            f"Webhook may arrive shortly."
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=pending"
            f"&installation_id={installation_id}"
        )

    return RedirectResponse(url=redirect_url)


@router.get("/oauth/callback")
async def github_user_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    github_service: GitHubUserOAuthService = Depends(get_github_user_oauth_service),
):
    if error:
        return await _github_oauth_failure_redirect(error, state)

    if not code:
        return await _github_oauth_failure_redirect("no_code", state)

    if not state:
        return RedirectResponse(
            url=build_oauth_completion_redirect(
                vendor="github",
                success=False,
                redirect_after=None,
                reason="missing_state",
            )
        )

    payload = await consume_oauth_state_payload(provider="github", state=state)
    if payload is None or payload.get("purpose") != "workflow_personal":
        return RedirectResponse(
            url=build_oauth_completion_redirect(
                vendor="github",
                success=False,
                redirect_after=None,
                reason="invalid_state",
            )
        )

    redirect_after = payload.get("redirect_after")
    try:
        token = await github_service.exchange_code_for_token(code)
        user = await github_service.get_authenticated_user(token.access_token)
        await run_in_threadpool(
            _persist_github_workflow_credential_db,
            token,
            user,
            payload,
            github_service,
        )
    except WorkflowCredentialAlreadyExists:
        return RedirectResponse(
            url=build_oauth_completion_redirect(
                vendor="github",
                success=False,
                redirect_after=redirect_after,
                reason="already_connected",
            )
        )
    except Exception:
        logger.exception("GitHub user OAuth callback failed")
        return RedirectResponse(
            url=build_oauth_completion_redirect(
                vendor="github",
                success=False,
                redirect_after=redirect_after,
                reason="internal_error",
            )
        )

    return RedirectResponse(
        url=build_oauth_completion_redirect(
            vendor="github",
            success=True,
            redirect_after=redirect_after,
        )
    )


def _persist_github_workflow_credential_db(
    token,
    user: dict,
    payload: dict,
    github_service: GitHubUserOAuthService,
) -> None:
    account_id = str(user.get("id") or user.get("login") or "")
    if not account_id:
        raise ValueError("GitHub user response missing id/login")

    login = user.get("login")
    with SessionLocal() as db:
        WorkflowCredentialService().create_personal_oauth(
            db,
            PersonalOAuthCredentialCreateRequest(
                vendor=WorkflowCredentialVendor.GITHUB,
                workspace_id=int(payload["workspace_id"]),
                user_id=int(payload["user_id"]),
                display_name=login or account_id,
                external_tenant_id="github.com",
                external_tenant_name="GitHub",
                external_account_id=account_id,
                external_account_name=login,
                external_account_email=user.get("email"),
                server_url=github_service.api_url,
                scopes=split_oauth_scopes(token.scope),
                token_payload={
                    "access_token": token.access_token,
                    "refresh_token": token.refresh_token,
                    "token_type": token.token_type,
                },
                extra_metadata={
                    "refresh_token_expires_in": token.refresh_token_expires_in,
                    "html_url": user.get("html_url"),
                },
                expires_in=token.expires_in,
            ),
        )


async def _github_oauth_failure_redirect(
    reason: str,
    state: str | None,
) -> RedirectResponse:
    return RedirectResponse(
        url=build_oauth_completion_redirect(
            vendor="github",
            success=False,
            redirect_after=await consume_workflow_redirect_after(
                provider="github",
                state=state,
            ),
            reason=reason,
        )
    )
