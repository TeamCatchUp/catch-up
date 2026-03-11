import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.connectors.github.schemas import (
    InstallationRepositoriesWebhookPayload,
    InstallationWebhookPayload,
)
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github import installation_repository as installation_crud
from catchup.db.github.domain_repository import RepositoryUpsertData
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import (
    GithubInstallationType,
    GithubRepositorySelection,
    KnowledgeSource,
    SourceType,
)
from catchup.db.workspaces import get_workspace_limit_one
from catchup.server.connector.webhook_verifier import WebhookVerifierProvider
from catchup.sync.incremental import ingest_record_changes, normalize_github_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["github-webhook"])


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def handle_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    payload_body = await request.body()

    verify_result = WebhookVerifierProvider.verify_github(
        payload_body=payload_body,
        signature_header=x_hub_signature_256,
        secret=settings.GITHUB_APP_WEBHOOK_SECRET,
    )
    if not verify_result.ok:
        logger.warning(
            "[WEBHOOK][GITHUB][VERIFY] Failed: reason=%s",
            verify_result.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Webhook Signature",
        )

    payload = await request.json()
    logger.info(
        "Received GitHub webhook: event=%s, action=%s",
        x_github_event,
        payload.get("action"),
    )

    if x_github_event == "ping":
        logger.info("Ping received from GitHub App: %s", payload.get("zen"))
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

    logger.warning("Unhandled webhook event: %s", x_github_event)
    return {"status": "ignored", "event": x_github_event}


async def _sync_installation_metadata(installation_id: int) -> None:
    try:
        with SessionLocal() as db:
            service = await create_github_ingestion_service(db, installation_id)
            await service.sync_installation_metadata(db)
    except Exception as exc:
        logger.error(
            "Failed to sync user and repository metadata for installation %s: %s",
            installation_id,
            exc,
        )


async def _register_knowledge_source(installation_id: int) -> None:
    def _sync_task() -> None:
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            if not workspace:
                logger.error("[GitHub] 등록된 워크스페이스가 없습니다. 관리자에게 문의하세요.")
                return

            existing_source = db.scalar(
                select(KnowledgeSource).where(
                    (KnowledgeSource.workspace_id == workspace.id)
                    & (KnowledgeSource.source_type == SourceType.GITHUB)
                    & (KnowledgeSource.external_identifier == str(installation_id))
                )
            )
            if existing_source:
                logger.info(
                    "[GitHub] 이미 등록된 지식 소스입니다. (installation_id=%s)",
                    installation_id,
                )
                return

            new_source = KnowledgeSource(
                workspace_id=workspace.id,
                source_type=SourceType.GITHUB,
                display_name="GitHub",
                external_identifier=str(installation_id),
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
    if action == "deleted":
        return await _handle_installation_deleted(data, db)
    if action == "suspended":
        return await _handle_installation_suspended(data, db)
    if action == "unsuspended":
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
        logger.info("Installation already exists: installation_id=%s", installation.id)
        return {"status": "exists", "installation_id": installation.id}

    account = installation.account
    repo_selection = None
    if installation.repository_selection:
        repo_selection = GithubRepositorySelection(installation.repository_selection)

    new_installation = installation_crud.create_installation(
        db=db,
        installation_id=installation.id,
        account_type=GithubInstallationType(account.type.lower()),
        account_id=account.id,
        account_login=account.login,
        account_avatar_url=account.avatar_url,
        repository_selection=repo_selection,
        suspended_at=installation.suspended_at,
    )

    logger.info(
        "Installation created: id=%s, account=%s",
        new_installation.installation_id,
        new_installation.account_login,
    )

    await _register_knowledge_source(installation.id)
    background_tasks.add_task(_sync_installation_metadata, installation.id)
    logger.info("Scheduled repository sync for installation %s", installation.id)

    return {"status": "created", "installation_id": new_installation.installation_id}


async def _handle_installation_deleted(
    data: InstallationWebhookPayload,
    db: Session,
) -> dict:
    installation_id = data.installation.id

    github_entities.delete_installation_repositories(db, installation_id)
    deleted = installation_crud.delete_installation_by_installation_id(db, installation_id)
    if deleted:
        logger.info("Installation deleted: installation_id=%s", installation_id)
        return {"status": "deleted", "installation_id": installation_id}

    logger.warning("Installation not found for deletion: installation_id=%s", installation_id)
    return {"status": "not_found", "installation_id": installation_id}


async def _handle_installation_suspended(
    data: InstallationWebhookPayload,
    db: Session,
) -> dict:
    installation = data.installation
    installation_crud.update_installation_suspended(db, installation.id, installation.suspended_at)
    logger.info("Installation suspended: installation_id=%s", installation.id)
    return {"status": "suspended", "installation_id": installation.id}


async def _handle_installation_unsuspended(
    data: InstallationWebhookPayload,
    db: Session,
    background_tasks: BackgroundTasks,
) -> dict:
    installation_id = data.installation.id
    installation_crud.update_installation_suspended(db, installation_id, None)
    logger.info("Installation unsuspended: installation_id=%s", installation_id)

    background_tasks.add_task(_sync_installation_metadata, installation_id)
    return {"status": "unsuspended", "installation_id": installation_id}


async def _handle_installation_repositories_event(
    payload: dict,
    db: Session,
) -> dict:
    data = InstallationRepositoriesWebhookPayload(**payload)
    installation_id = data.installation.id

    logger.info(
        "Installation repositories changed: installation=%s, added=%s, removed=%s",
        installation_id,
        len(data.repositories_added),
        len(data.repositories_removed),
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
        logger.info("Added %s repositories", len(data.repositories_added))

    for repo in data.repositories_removed:
        full_name = repo.get("full_name", "")
        if full_name:
            github_entities.delete_repository(db, installation_id, full_name)
            logger.info("Removed repository: %s", full_name)

    return {
        "status": "processed",
        "installation_id": installation_id,
        "added": len(data.repositories_added),
        "removed": len(data.repositories_removed),
    }
