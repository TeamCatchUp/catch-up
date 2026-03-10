import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.github.schemas import(
     InstallationRepositoriesWebhookPayload, InstallationWebhookPayload
)
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.workspaces import get_workspace_limit_one
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.configs.config import auth_settings, settings
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.github import installation_repository as installation_crud
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.domain_repository import RepositoryUpsertData
from catchup.db.models import GithubInstallationType, GithubRepositorySelection, KnowledgeSource, SourceType
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.incremental import ingest_record_changes, normalize_github_event

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

    verify_result = WebhookVerifierProvider.verify_github(
        payload_body=payload_body,
        signature_header=x_hub_signature_256,
        secret=settings.GITHUB_APP_WEBHOOK_SECRET,
    )
    if not verify_result.ok:
        logger.warning(
            f"[WEBHOOK][GITHUB][VERIFY] Failed: reason={verify_result.reason}"
        )
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
    
    if x_github_event in {"issues", "pull_request"}:
        changes = normalize_github_event(
            event_name=x_github_event,
            payload=payload,
        )
        if not changes:
            return {"status": "ignored", "event": x_github_event, "reason": "unsupported_payload"}
        record_keys = ingest_record_changes(db, changes)
        logger.info(
            "Accepted GitHub incremental webhook: event=%s, record_keys=%s",
            x_github_event,
            record_keys,
        )
        return {"status": "accepted", "event": x_github_event, "record_keys": record_keys}

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


async def _sync_installation_metadata(installation_id: int) -> None:
    """
    Background Task: Installation 메타데이터 동기화 (Users + Repositories)

    - Organization인 경우: 멤버 목록 + Repository 목록
    - User인 경우: 해당 User + Repository 목록
    """
    try:
        with SessionLocal() as db:
            service = await create_github_ingestion_service(db, installation_id)
            await service.sync_installation_metadata(db)
    
    except Exception as e:
        logger.error(f"Failed to Sync User+Repository metadata for installation {installation_id} : {e}")


# =============================================================================
# Private Helper Functions
# =============================================================================
async def _register_knowledge_source(installation_id: int):
    def _sync_task():
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            
            if not workspace:
                logger.error("[GitHub] 등록된 워크스페이스가 없습니다. 관리자에게 문의하세요.")
                return
            
            # 중복 등록 방지
            existing_source = db.scalar(
                select(KnowledgeSource).where(
                    (KnowledgeSource.workspace_id == workspace.id) &
                    (KnowledgeSource.source_type == SourceType.GITHUB) &
                    (KnowledgeSource.external_identifier == str(installation_id))
                )
            )
            
            if existing_source:
                logger.info(f"[GitHub] 이미 등록된 지식 소스입니다. (installation_id={installation_id})")
                return
            
            new_source = KnowledgeSource(
                workspace_id=workspace.id,
                source_type=SourceType.GITHUB,
                display_name="GitHub",
                external_identifier=str(installation_id)    
            )
            add_knowledge_source(db, new_source)
            db.commit()
    await run_in_threadpool(_sync_task)


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

    account = data.installation.account
    installation_info = data.installation

    repo_selection = None
    if installation_info.repository_selection:
        repo_selection = GithubRepositorySelection(installation_info.repository_selection)

    new_installation = installation_crud.create_installation(
    db=db,
    installation_id=installation_info.id,
    account_type=GithubInstallationType(account.type.lower()),
    account_id=account.id,
    account_login=account.login,
    account_avatar_url=account.avatar_url,
    repository_selection=repo_selection,
    suspended_at=installation_info.suspended_at,
)

    logger.info(
        f"Installation Created: id={new_installation.installation_id}, "
        f"account={new_installation.account_login}"
    )
    
    await _register_knowledge_source(installation.id)

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
        repos_dto = [
            RepositoryUpsertData(
                repo_id=repo.get("id", 0),
                owner=repo.get("owner", {}).get("login", "") if isinstance(repo.get("owner"), dict) else "",
                name=repo.get("name", ""),
                full_name=repo.get("full_name", ""),
                html_url=repo.get("html_url", ""),
                description=repo.get("description"),
                default_branch=repo.get("default_branch", "main"),
                language=repo.get("language"),
                topics=repo.get("topics", []),
                stargazers_count=repo.get("stargazers_count", 0),
                forks_count=repo.get("forks_count", 0),
                open_issues_count=repo.get("open_issues_count", 0),
                private=repo.get("private", False),
                archived=repo.get("archived", False),
                disabled=repo.get("disabled", False),
                pushed_at=repo.get("pushed_at"),
                repo_created_at=repo.get("created_at"),
                repo_updated_at=repo.get("updated_at"),
            )
            for repo in data.repositories_added
        ]
        github_entities.upsert_repositories_bulk(db, installation_id, repos_dto)
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
