from __future__ import annotations

from typing import Any

import structlog
from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from catchup.audit.actions import IntegrationAction
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.audit.utils import audit_log
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.connectors.github.schemas import InstallationRepositoriesWebhookPayload
from catchup.connectors.github.schemas import InstallationWebhookPayload
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github import installation_repository as installation_crud
from catchup.db.github.domain_repository import RepositoryUpsertData
from catchup.db.knowledge_source import add_knowledge_source
from catchup.db.models import GithubInstallationType
from catchup.db.models import GithubRepositorySelection
from catchup.db.models import KnowledgeSource
from catchup.db.models import SourceType
from catchup.db.workspaces import get_workspace_limit_one
from catchup.events.enums import EventType
from catchup.events.enums import IntegrationEventAction
from catchup.sync.common.exceptions import BaseSyncException
from catchup.sync.ingress.types import GithubWebhookRequest
from catchup.sync.ingress.types import GithubWebhookResponse

from catchup.connectors.github.webhook.responses import ignored_event_response
from catchup.connectors.github.webhook.responses import installation_repositories_response
from catchup.connectors.github.webhook.responses import installation_status_response
from catchup.connectors.github.webhook.responses import processed_metadata_response

logger = structlog.get_logger(__name__)

_REPOSITORY_REFRESH_EVENTS = frozenset({
    "repository",
})

_USER_REFRESH_EVENTS = frozenset({
    "organization",
    "membership",
    "member",
})


async def handle_metadata_event(
    request: GithubWebhookRequest,
    background_tasks: BackgroundTasks,
) -> GithubWebhookResponse:
    if request.event_name == "installation":
        data = InstallationWebhookPayload(**request.payload)
        if not _is_supported_installation_action(data.action):
            return ignored_event_response(
                event=request.event_name,
                reason="unsupported_action",
                action=data.action,
            )

        return await _handle_installation_event(
            data=data,
            background_tasks=background_tasks,
        )

    if request.event_name == "installation_repositories":
        return await run_in_threadpool(
            _handle_installation_repositories_event,
            request.payload,
        )

    installation_id = _extract_installation_id(request.payload)
    if installation_id is None:
        return ignored_event_response(
            event=request.event_name,
            reason="missing_installation_id",
        )

    logger.info(
        "github_metadata_refresh_started",
        event_name=request.event_name,
        installation_id=installation_id,
    )
    _schedule_metadata_sync(background_tasks, installation_id)

    refresh_target = "repositories" if request.event_name in _REPOSITORY_REFRESH_EVENTS else "users"
    if request.event_name not in _REPOSITORY_REFRESH_EVENTS | _USER_REFRESH_EVENTS:
        refresh_target = "metadata"

    return processed_metadata_response(
        event=request.event_name,
        installation_id=installation_id,
        refresh_target=refresh_target,
    )


@audit_log(
    IntegrationAction.HANDLE_INSTALLATION,
    metadata_factory=IntegrationAuditMetadata.from_audit,
    emit_attempt=True,
)
async def _handle_installation_event(
    *,
    data: InstallationWebhookPayload,
    background_tasks: BackgroundTasks,
) -> GithubWebhookResponse:
    action = data.action
    installation_id = data.installation.id

    if action == "created":
        return await _handle_installation_created(
            data=data,
            background_tasks=background_tasks,
        )

    if action == "deleted":
        return await run_in_threadpool(_handle_installation_deleted, data)

    if action == "suspended":
        return await run_in_threadpool(_handle_installation_suspended, data)

    if action == "unsuspended":
        result = await run_in_threadpool(_handle_installation_unsuspended, data)
        _schedule_metadata_sync(background_tasks, installation_id)
        return result

    raise ValueError(f"unsupported github installation action: {action}")


async def _handle_installation_created(
    data: InstallationWebhookPayload,
    background_tasks: BackgroundTasks,
) -> GithubWebhookResponse:
    result = await run_in_threadpool(
        _create_installation,
        data,
    )

    if result.status != "created":
        return result

    await _register_knowledge_source(result.installation_id)
    _schedule_metadata_sync(background_tasks, result.installation_id)

    return result


def _create_installation(
    data: InstallationWebhookPayload,
) -> GithubWebhookResponse:
    installation = data.installation

    with SessionLocal() as db:
        existing = installation_crud.get_installation_by_installation_id(
            db,
            installation.id,
        )
        if existing:
            return installation_status_response(
                status="exists",
                installation_id=installation.id,
            )

        account = installation.account
        repository_selection = None
        if installation.repository_selection:
            repository_selection = GithubRepositorySelection(
                installation.repository_selection
            )

        installation_crud.create_installation(
            db=db,
            installation_id=installation.id,
            account_type=GithubInstallationType(account.type.lower()),
            account_id=account.id,
            account_login=account.login,
            account_avatar_url=account.avatar_url,
            repository_selection=repository_selection,
            suspended_at=installation.suspended_at,
        )
        db.commit()

    emit_audit_event(
        event_type=EventType.INTEGRATION,
        event_action=IntegrationEventAction.OAUTH_TOKEN_PERSISTED,
        event_status=AuditEventStatus.SUCCESS,
        level=AuditLevel.INFO,
        metadata=IntegrationAuditMetadata(
            context=f"github_installation_persisted:installation_id={installation.id}",
            provider="github",
        ),
        immediate=True,
    )
    return installation_status_response(
        status="created",
        installation_id=installation.id,
    )


def _handle_installation_deleted(
    data: InstallationWebhookPayload,
) -> GithubWebhookResponse:
    installation_id = data.installation.id

    with SessionLocal() as db:
        github_entities.delete_installation_repositories(db, installation_id)
        deleted = installation_crud.delete_installation_by_installation_id(
            db,
            installation_id,
        )
        db.commit()

    if deleted:
        return installation_status_response(
            status="deleted",
            installation_id=installation_id,
        )

    return installation_status_response(
        status="not_found",
        installation_id=installation_id,
    )


def _handle_installation_suspended(
    data: InstallationWebhookPayload,
) -> GithubWebhookResponse:
    installation = data.installation

    with SessionLocal() as db:
        installation_crud.update_installation_suspended(
            db,
            installation.id,
            installation.suspended_at,
        )
        db.commit()

    return installation_status_response(
        status="suspended",
        installation_id=installation.id,
    )


def _handle_installation_unsuspended(
    data: InstallationWebhookPayload,
) -> GithubWebhookResponse:
    installation_id = data.installation.id

    with SessionLocal() as db:
        installation_crud.update_installation_suspended(
            db,
            installation_id,
            None,
        )
        db.commit()

    return installation_status_response(
        status="unsuspended",
        installation_id=installation_id,
    )


def _handle_installation_repositories_event(
    payload: dict[str, Any],
) -> GithubWebhookResponse:
    data = InstallationRepositoriesWebhookPayload(**payload)
    installation_id = data.installation.id

    with SessionLocal() as db:
        if data.repositories_added:
            github_entities.upsert_repositories_bulk(
                db,
                installation_id,
                [
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
                ],
            )

        for repo in data.repositories_removed:
            full_name = repo.get("full_name", "")
            if full_name:
                github_entities.delete_repository(db, installation_id, full_name)

        db.commit()

    return installation_repositories_response(
        installation_id=installation_id,
        added=len(data.repositories_added),
        removed=len(data.repositories_removed),
    )


async def _sync_installation_metadata(installation_id: int) -> None:
    try:
        service = await create_github_ingestion_service(installation_id)
        await service.sync_installation_metadata()
    except BaseSyncException as exc:
        logger.warning(
            "github_metadata_sync_failed",
            installation_id=installation_id,
            code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.error(
            "github_metadata_sync_failed",
            installation_id=installation_id,
            error=str(exc),
            exc_info=True,
        )


async def _register_knowledge_source(installation_id: int) -> None:
    def _sync_task() -> None:
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            if not workspace:
                logger.error("github_workspace_not_found")
                return

            existing = db.scalar(
                select(KnowledgeSource).where(
                    (KnowledgeSource.workspace_id == workspace.id)
                    & (KnowledgeSource.source_type == SourceType.GITHUB)
                    & (KnowledgeSource.external_identifier == str(installation_id))
                )
            )
            if existing:
                return

            add_knowledge_source(
                db,
                KnowledgeSource(
                    workspace_id=workspace.id,
                    source_type=SourceType.GITHUB,
                    display_name="GitHub",
                    external_identifier=str(installation_id),
                ),
            )
            db.commit()

    await run_in_threadpool(_sync_task)


def _extract_installation_id(payload: dict[str, Any]) -> int | None:
    installation = payload.get("installation") or {}
    raw = installation.get("id")
    if raw in (None, ""):
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _schedule_metadata_sync(
    background_tasks: BackgroundTasks,
    installation_id: int,
) -> None:
    background_tasks.add_task(_sync_installation_metadata, installation_id)


def _is_supported_installation_action(action: str) -> bool:
    return action in {"created", "deleted", "suspended", "unsuspended"}
