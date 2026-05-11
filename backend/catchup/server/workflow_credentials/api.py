from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.connectors.atlassian.oauth_client import get_atlassian_oauth_client
from catchup.connectors.github.auth import get_github_user_oauth_service
from catchup.connectors.slack.auth import get_slack_oauth_service
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.models import User
from catchup.db.models import UserWorkspace
from catchup.security.credential_crypto import CredentialCryptoError
from catchup.security.credential_crypto import (
    ensure_workflow_credential_encryption_ready,
)
from catchup.utils.redis import store_oauth_state_payload
from catchup.workflow_credentials.oauth import sanitize_redirect_after
from catchup.workflow_credentials.schemas import WorkflowCredentialListResponse
from catchup.workflow_credentials.schemas import WorkflowCredentialResponse
from catchup.workflow_credentials.service import WorkflowCredentialService

router = APIRouter(
    prefix="/api/v1/workflow-credentials",
    tags=["workflow-credentials"],
)


@router.get("", response_model=WorkflowCredentialListResponse)
def list_workflow_credentials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return WorkflowCredentialListResponse(
        items=[
            WorkflowCredentialResponse.model_validate(credential)
            for credential in WorkflowCredentialService().list_for_user(
                db,
                user_id=current_user.id,
            )
        ]
    )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow_credential(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not WorkflowCredentialService().delete_for_user(
        db,
        credential_id=credential_id,
        user_id=current_user.id,
    ):
        raise HTTPException(status_code=404, detail="Workflow credential not found")
    return None


@router.get("/slack/oauth/authorize")
async def authorize_slack_workflow_credential(
    workspace_id: str = Query(...),
    redirect_after: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    return await _authorize_workflow_credential(
        vendor="slack",
        workspace_id=workspace_id,
        redirect_after=redirect_after,
        current_user=current_user,
        build_authorization_url=get_slack_oauth_service().get_user_authorization_url,
    )


@router.get("/github/oauth/authorize")
async def authorize_github_workflow_credential(
    workspace_id: str = Query(...),
    redirect_after: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    return await _authorize_workflow_credential(
        vendor="github",
        workspace_id=workspace_id,
        redirect_after=redirect_after,
        current_user=current_user,
        build_authorization_url=get_github_user_oauth_service().get_authorization_url,
    )


@router.get("/atlassian/oauth/authorize")
async def authorize_atlassian_workflow_credential(
    workspace_id: str = Query(...),
    redirect_after: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    return await _authorize_workflow_credential(
        vendor="atlassian",
        workspace_id=workspace_id,
        redirect_after=redirect_after,
        current_user=current_user,
        build_authorization_url=get_atlassian_oauth_client().get_authorization_url,
    )


async def _authorize_workflow_credential(
    *,
    vendor: str,
    workspace_id: str,
    redirect_after: str | None,
    current_user: User,
    build_authorization_url: Callable[[str], str],
) -> RedirectResponse:
    workspace_id_int = _parse_workspace_id(workspace_id)
    await run_in_threadpool(
        _require_workspace_membership,
        current_user.id,
        workspace_id_int,
    )
    state = await _store_personal_oauth_state(
        vendor=vendor,
        user_id=current_user.id,
        workspace_id=workspace_id_int,
        redirect_after=redirect_after,
    )
    return RedirectResponse(url=build_authorization_url(state))


def _parse_workspace_id(workspace_id: str) -> int:
    try:
        parsed = int(workspace_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="workspace_id must be an integer")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail="workspace_id must be positive")
    return parsed


def _require_workspace_membership(user_id: int, workspace_id: int) -> None:
    with SessionLocal() as db:
        membership = db.scalar(
            select(UserWorkspace).where(
                UserWorkspace.user_id == user_id,
                UserWorkspace.workspace_id == workspace_id,
            )
        )
    if membership is None:
        raise HTTPException(status_code=403, detail="Workspace access denied")


async def _store_personal_oauth_state(
    *,
    vendor: str,
    user_id: int,
    workspace_id: int,
    redirect_after: str | None,
) -> str:
    try:
        ensure_workflow_credential_encryption_ready()
    except CredentialCryptoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Workflow credential encryption is not configured",
        ) from exc

    state = secrets.token_urlsafe(32)
    await store_oauth_state_payload(
        provider=vendor,
        state=state,
        payload={
            "purpose": "workflow_personal",
            "vendor": vendor,
            "user_id": user_id,
            "workspace_id": workspace_id,
            "redirect_after": sanitize_redirect_after(redirect_after),
        },
    )
    return state
