import hashlib
import hmac
import logging
from math import log
from re import A
from typing import Optional

from catchup.auth.github.schemas import InstallationRepositoriesWebhookPayload, InstallationWebhookPayload
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.dependencies import get_db
from catchup.db import github_installation as installation_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix = "/api/v1/github", tags = ["GitHub Connector"])

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

    if x_github_event == "installation":
        return await _handle_installation_event(payload, db)
    
    return {"status": "ignored", "event": x_github_event}

async def _handle_installation_event(db: Session, payload: dict):
    data = InstallationWebhookPayload(**payload)
    installation = data.installation
    action = data.action

    if action == "created":
        existing = installation_crud.get_installation_by_installation_id(db, installation.id)
        if existing:
            logger.info(f"Installation already exists: installation_id={installation.id}")
            return {"status": "exists", "installation_id": installation.id}
        
        new_installation = installation_crud.create_installation(db = db, payload = data)
        logger.info(
            f"Installation Created : id = {new_installation.installation_id}"
            f"account = {new_installation.account_login}"
        )
        return {"status": "created", "installation_id": new_installation.installation_id}

    elif action == "deleted":
        deleted = installation_crud.delete_installation_by_installation_id(db, installation.id)
        if deleted:
            logger.info(f"Installation Deleted : installation_id = {installation.id}")
            return {"status": "deleted", "installation_id": installation.id}
        else:
            logger.warning(f"Installation Not Found for Deletion : installation_id = {installation.id}")
            return {"status": "not_found", "installation_id": installation.id}
        
    elif action == "suspended":
        installation_crud.update_installation_suspended(
            db, installation.id, installation.suspended_at
        )
        logger.info(f"Installation Suspended : installation_id = {installation.id}")
        return {"status": "suspended", "installation_id": installation.id}
    
    elif action == "unsuspended":
        installation_crud.update_installation_suspended(
            db, installation.id, None
        )
        logger.info(f"Installation Unsuspended : installation_id = {installation.id}")
        return {"status": "unsuspended", "installation_id": installation.id}
    
    return {"status": "ignored", "action": action}

async def _handle_installation_repositories_event(payload: dict):
    data = InstallationRepositoriesWebhookPayload(**payload)

    logger.info(
        f"Installation repositories changed: "
        f"installation={data.installation.id}, "
        f"added={len(data.repositories_added)}, "
        f"removed={len(data.repositories_removed)}"
    )
    
    # TODO: 나중에 실시간 동기화 구현 시 처리
    return {
        "status": "logged",
        "installation_id": data.installation.id,
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
            "account_login": inst.account_login,
            "account_id": inst.account_id,
            "repository_selection": inst.repository_selection,
            "created_at": inst.created_at,
            "suspended_at": inst.suspended_at,
        }
        for inst in installations
    ]
    