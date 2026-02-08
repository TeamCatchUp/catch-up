import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from catchup.auth.github.schemas import InstallationRepositoriesWebhookPayload, InstallationWebhookPayload
from catchup.auth.github.app import get_github_app_service
from catchup.components.connectors.github.client import GitHubApiClient
from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db import github_installation as installation_crud
from catchup.db import github_entities

logger = logging.getLogger(__name__)

router = APIRouter(prefix = "/api/v1/github", tags = ["GitHub Connector"])


# ============================================================
# Background Task: Repository 동기화
# ============================================================

async def sync_installation_repositories(installation_id: int) -> None:
    """
    Installation에 접근 가능한 Repository 목록을 가져와서 RDBMS에 저장

    Background task로 실행되어 Webhook 응답을 지연시키지 않음.
    """
    try:
        logger.info(f"Starting repository sync for installation {installation_id}")

        # Installation Access Token 발급
        github_app_service = get_github_app_service()
        access_token = await github_app_service.get_installation_access_token(installation_id)

        # GitHub API 클라이언트로 레포 목록 조회
        client = GitHubApiClient(access_token)
        repos_data = await client.list_installation_repos()

        logger.info(f"Found {len(repos_data)} repositories for installation {installation_id}")

        # RDBMS에 저장 (동기 작업이므로 새 세션 필요)
        from catchup.db.engine import SessionLocal
        with SessionLocal() as db:
            count = github_entities.upsert_repositories_bulk(db, installation_id, repos_data)
            logger.info(f"Saved {count} repositories for installation {installation_id}")

    except Exception as e:
        logger.error(f"Failed to sync repositories for installation {installation_id}: {e}")

def verify_webhook_signature(
        payload_body: bytes,
        signature_header: Optional[str],
        secret: str) -> bool:
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
    # 1. Payload 읽기
    payload_body = await request.body()

    # 2. Signature 검증
    if not verify_webhook_signature(
        payload_body,
        x_hub_signature_256,
        settings.GITHUB_APP_WEBHOOK_SECRET
    ):
        logger.warning("Invalid Webhook Signature Recieved")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Webhook Signature"
        )

    # 3. Event Type에 따른 처리
    payload = await request.json()

    logger.info(f"Received GitHub webhook: event={x_github_event}, action={payload.get('action')}")

    # ping 이벤트 처리 (webhook 설정 시 GitHub이 보내는 테스트 요청)
    if x_github_event == "ping":
        logger.info(f"Ping received from GitHub App: {payload.get('zen')}")
        return {"status": "pong", "zen": payload.get("zen")}

    if x_github_event == "installation":
        return await _handle_installation_event(payload, db, background_tasks)

    if x_github_event == "installation_repositories":
        return await _handle_installation_repositories_event(payload, db)

    logger.warning(f"Unhandled webhook event: {x_github_event}")
    return {"status": "ignored", "event": x_github_event}

async def _handle_installation_event(
    payload: dict,
    db: Session,
    background_tasks: BackgroundTasks,
):
    data = InstallationWebhookPayload(**payload)
    installation = data.installation
    action = data.action

    if action == "created":
        existing = installation_crud.get_installation_by_installation_id(db, installation.id)
        if existing:
            logger.info(f"Installation already exists: installation_id={installation.id}")
            return {"status": "exists", "installation_id": installation.id}

        new_installation = installation_crud.create_installation(db=db, payload=data)
        logger.info(
            f"Installation Created: id={new_installation.installation_id}, "
            f"account={new_installation.account_login}"
        )

        # Background task로 Repository 목록 동기화
        background_tasks.add_task(sync_installation_repositories, installation.id)
        logger.info(f"Scheduled repository sync for installation {installation.id}")

        return {"status": "created", "installation_id": new_installation.installation_id}

    elif action == "deleted":
        # Installation 삭제 시 관련 Repository도 삭제
        github_entities.delete_installation_repositories(db, installation.id)
        deleted = installation_crud.delete_installation_by_installation_id(db, installation.id)
        if deleted:
            logger.info(f"Installation Deleted: installation_id={installation.id}")
            return {"status": "deleted", "installation_id": installation.id}
        else:
            logger.warning(f"Installation Not Found for Deletion: installation_id={installation.id}")
            return {"status": "not_found", "installation_id": installation.id}

    elif action == "suspended":
        installation_crud.update_installation_suspended(
            db, installation.id, installation.suspended_at
        )
        logger.info(f"Installation Suspended: installation_id={installation.id}")
        return {"status": "suspended", "installation_id": installation.id}

    elif action == "unsuspended":
        installation_crud.update_installation_suspended(
            db, installation.id, None
        )
        logger.info(f"Installation Unsuspended: installation_id={installation.id}")

        # Unsuspend 시에도 Repository 목록 갱신
        background_tasks.add_task(sync_installation_repositories, installation.id)

        return {"status": "unsuspended", "installation_id": installation.id}

    return {"status": "ignored", "action": action}

async def _handle_installation_repositories_event(
    payload: dict,
    db: Session,
):
    data = InstallationRepositoriesWebhookPayload(**payload)
    installation_id = data.installation.id

    logger.info(
        f"Installation repositories changed: "
        f"installation={installation_id}, "
        f"added={len(data.repositories_added)}, "
        f"removed={len(data.repositories_removed)}"
    )

    # 추가된 Repository 저장
    if data.repositories_added:
        github_entities.upsert_repositories_bulk(
            db, installation_id, data.repositories_added
        )
        logger.info(f"Added {len(data.repositories_added)} repositories")

    # 삭제된 Repository 제거
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
    