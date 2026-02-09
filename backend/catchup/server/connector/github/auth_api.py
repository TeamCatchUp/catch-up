import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from catchup.connectors.github.schemas import InstallationRepositoriesWebhookPayload, InstallationWebhookPayload
from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.client import GitHubApiClient
from catchup.configs.config import auth_settings, settings
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db import github_installation as installation_crud
from catchup.db import github_entities
from catchup.db.models import GithubInstallationType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["GitHub Connector"])


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    """
    Github App Webhook 수신 Endpoint
    - installation : created, deleted, suspended
    - installation_repositories : added, removed
    """
    payload_body = await request.body()

    if not _verify_webhook_signature(
        payload_body,
        x_hub_signature_256,
        settings.GITHUB_APP_WEBHOOK_SECRET
    ):
        logger.warning("Invalid Webhook Signature Recieved")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Webhook Signature"
        )

    payload = await request.json()
    logger.info(f"Received GitHub webhook: event={x_github_event}, action={payload.get('action')}")

    if x_github_event == "ping":
        logger.info(f"Ping received from GitHub App: {payload.get('zen')}")
        return {"status": "pong", "zen": payload.get("zen")}

    if x_github_event == "installation":
        return await _handle_installation_event(payload, db, background_tasks)

    if x_github_event == "installation_repositories":
        return await _handle_installation_repositories_event(payload, db)

    logger.warning(f"Unhandled webhook event: {x_github_event}")
    return {"status": "ignored", "event": x_github_event}


@router.get("/installations")
async def list_installations(db: Session = Depends(get_db)):
    """
    등록된 모든 Installation 목록 조회
    """
    installations = installation_crud.get_all_installations(db)
    return [
        {
            "installation_id": inst.installation_id,
            "account_type": inst.account_type,
            "account_login": inst.account_login,
            "account_id": inst.account_id,
            "repository_selection": inst.repository_selection,
            "created_at": inst.created_at,
            "suspended_at": inst.suspended_at,
        }
        for inst in installations
    ]


@router.get("/install")
async def github_app_install_callback(
    installation_id: Optional[int] = Query(None),
    setup_action: Optional[str] = Query(None),
    db: Session = Depends(get_db),
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

    installation = installation_crud.get_installation_by_installation_id(db, installation_id)

    if installation:
        logger.info(
            f"GitHub App installation found: "
            f"installation_id={installation_id}, account={installation.account_login}"
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=success"
            f"&installation_id={installation_id}"
            f"&account={installation.account_login}"
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


# =============================================================================
# Utility Functions
# =============================================================================

def _verify_webhook_signature(
    payload_body: bytes,
    signature_header: Optional[str],
    secret: str,
) -> bool:
    """
    Github Webhook Signature 검증
    - X-Hub-Signature-256 헤더와 payload를 HMAC SHA256으로 비교
    """
    if not signature_header:
        return False

    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


async def _sync_installation_metadata(installation_id: int) -> None:
    """
    Background Task: Installation 메타데이터 동기화 (Users + Repositories)

    - Organization인 경우: 멤버 목록 + Repository 목록
    - User인 경우: 해당 User + Repository 목록
    """
    try:
        logger.info(f"Starting metadata sync for installation {installation_id}")

        github_app_service = get_github_app_service()
        access_token = await github_app_service.get_installation_access_token(installation_id)
        client = GitHubApiClient(access_token)

        with SessionLocal() as db:
            # Installation 정보 조회
            installation = installation_crud.get_installation_by_installation_id(db, installation_id)
            if not installation:
                logger.warning(f"Installation {installation_id} not found in DB")
                return

            account_login = installation.account_login
            account_type = installation.account_type

            # 1. User 동기화
            users_data = []
            if account_type == GithubInstallationType.ORGANIZATION:
                try:
                    members = await client.list_org_members_graphql(account_login)
                    users_data.extend(members)
                    logger.info(f"Found {len(members)} members in organization '{account_login}'")
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch org members for '{account_login}': {e}. "
                        "Organization members permission may be required."
                    )
            else:
                try:
                    user_info = await client.get_user(account_login)
                    if user_info:
                        users_data.append({
                            "database_id": user_info.get("id"),
                            "login": user_info.get("login"),
                            "name": user_info.get("name"),
                            "email": user_info.get("email"),
                            "avatar_url": user_info.get("avatar_url"),
                            "org_role": None,
                        })
                        logger.info(f"Found user '{account_login}'")
                except Exception as e:
                    logger.warning(f"Failed to fetch user '{account_login}': {e}")

            if users_data:
                user_count = github_entities.upsert_users_bulk(db, users_data)
                logger.info(f"Saved {user_count} users for installation {installation_id}")

            # 2. Repository 동기화
            repos_data = await client.list_installation_repos()
            logger.info(f"Found {len(repos_data)} repositories for installation {installation_id}")

            repo_count = github_entities.upsert_repositories_bulk(db, installation_id, repos_data)
            logger.info(f"Saved {repo_count} repositories for installation {installation_id}")

    except Exception as e:
        logger.error(f"Failed to sync metadata for installation {installation_id}: {e}")


# =============================================================================
# Private Helper Functions
# =============================================================================

async def _handle_installation_event(
    payload: dict,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    data = InstallationWebhookPayload(**payload)
    action = data.action

    if action == "created":
        return await _handle_installation_created(data, db, background_tasks)
    elif action == "deleted":
        return await _handle_installation_deleted(data, db)
    elif action == "suspended":
        return await _handle_installation_suspended(data, db)
    elif action == "unsuspended":
        return await _handle_installation_unsuspended(data, db, background_tasks)

    return {"status": "ignored", "action": action}


async def _handle_installation_created(
    data: InstallationWebhookPayload,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    installation = data.installation

    existing = installation_crud.get_installation_by_installation_id(db, installation.id)
    if existing:
        logger.info(f"Installation already exists: installation_id={installation.id}")
        return {"status": "exists", "installation_id": installation.id}

    new_installation = installation_crud.create_installation(db=db, payload=data)
    logger.info(
        f"Installation Created: id={new_installation.installation_id}, "
        f"account={new_installation.account_login}"
    )

    background_tasks.add_task(_sync_installation_metadata, installation.id)
    logger.info(f"Scheduled repository sync for installation {installation.id}")

    return {"status": "created", "installation_id": new_installation.installation_id}


async def _handle_installation_deleted(
    data: InstallationWebhookPayload,
    db: Session,
) -> dict:
    installation_id = data.installation.id

    github_entities.delete_installation_repositories(db, installation_id)
    deleted = installation_crud.delete_installation_by_installation_id(db, installation_id)

    if deleted:
        logger.info(f"Installation Deleted: installation_id={installation_id}")
        return {"status": "deleted", "installation_id": installation_id}

    logger.warning(f"Installation Not Found for Deletion: installation_id={installation_id}")
    return {"status": "not_found", "installation_id": installation_id}


async def _handle_installation_suspended(
    data: InstallationWebhookPayload,
    db: Session,
) -> dict:
    installation = data.installation

    installation_crud.update_installation_suspended(db, installation.id, installation.suspended_at)
    logger.info(f"Installation Suspended: installation_id={installation.id}")

    return {"status": "suspended", "installation_id": installation.id}


async def _handle_installation_unsuspended(
    data: InstallationWebhookPayload,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    installation_id = data.installation.id

    installation_crud.update_installation_suspended(db, installation_id, None)
    logger.info(f"Installation Unsuspended: installation_id={installation_id}")

    background_tasks.add_task(_sync_installation_metadata, installation_id)

    return {"status": "unsuspended", "installation_id": installation_id}


async def _handle_installation_repositories_event(
    payload: dict,
    db: Session,
) -> dict:
    data = InstallationRepositoriesWebhookPayload(**payload)
    installation_id = data.installation.id

    logger.info(
        f"Installation repositories changed: "
        f"installation={installation_id}, "
        f"added={len(data.repositories_added)}, "
        f"removed={len(data.repositories_removed)}"
    )

    if data.repositories_added:
        github_entities.upsert_repositories_bulk(
            db, installation_id, data.repositories_added
        )
        logger.info(f"Added {len(data.repositories_added)} repositories")

    for repo in data.repositories_removed:
        full_name = repo.get("full_name", "")
        if full_name:
            github_entities.delete_repository(db, installation_id, full_name)
            logger.info(f"Removed repository: {full_name}")

    return {
        "status": "processed",
        "installation_id": installation_id,
        "added": len(data.repositories_added),
        "removed": len(data.repositories_removed),
    }