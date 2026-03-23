from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.audit.metadata import IntegrationAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.connectors.github.schemas import (
    InstallationRepositoriesWebhookPayload,
    InstallationWebhookPayload,
)
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
from catchup.events.enums import EventType, IntegrationEventAction
from catchup.sync.common.exceptions import SyncAPIError

from .responses import (
    ignored_event_response,
    installation_repositories_response,
    installation_status_response,
    processed_metadata_response,
)

logger = logging.getLogger(__name__)

ScheduleTask = Callable[..., None]

_REPOSITORY_REFRESH_EVENTS = frozenset({
    "repository",
})

_USER_REFRESH_EVENTS = frozenset({
    "organization",
    "membership",
    "member",
})


async def handle_metadata_event(
    *,
    event_name: str,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    if event_name == "installation":
        return await _handle_installation_event(
            payload=payload,
            schedule_task=schedule_task,
        )

    if event_name == "installation_repositories":
        return await run_in_threadpool(
            _handle_installation_repositories_event,
            payload,
        )

    installation_id = _extract_installation_id(payload)
    if installation_id is None:
        return ignored_event_response(
            event=event_name,
            reason="missing_installation_id",
        )

    logger.info(
        "[GITHUB][WEBHOOK][INGRESS] Metadata refresh scheduled: event=%s, installation_id=%s",
        event_name,
        installation_id,
    )
    schedule_task(_sync_installation_metadata, installation_id)

    refresh_target = "repositories" if event_name in _REPOSITORY_REFRESH_EVENTS else "users"
    if event_name not in _REPOSITORY_REFRESH_EVENTS | _USER_REFRESH_EVENTS:
        refresh_target = "metadata"

    return processed_metadata_response(
        event=event_name,
        installation_id=installation_id,
        refresh_target=refresh_target,
    )


async def _handle_installation_event(
    *,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    data = InstallationWebhookPayload(**payload)
    action = data.action
    installation_id = data.installation.id
    context = f"github_installation_created:installation_id={installation_id}:event_name=installation"

    if action == "created":
        metadata = IntegrationAuditMetadata(
            context=context,
            provider="github",
        )
        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.INSTALLATION_EVENT_RECEIVED,
            event_status=AuditEventStatus.ATTEMPT,
            level=AuditLevel.INFO,
            metadata=metadata,
            immediate=True,
        )
        try:
            result = await _handle_installation_created(
                data=data,
                schedule_task=schedule_task,
            )
        except Exception:
            emit_audit_event(
                event_type=EventType.INTEGRATION,
                event_action=IntegrationEventAction.INSTALLATION_EVENT_RECEIVED,
                event_status=AuditEventStatus.FAIL,
                level=AuditLevel.ERROR,
                metadata=metadata,
                immediate=True,
            )
            raise

        emit_audit_event(
            event_type=EventType.INTEGRATION,
            event_action=IntegrationEventAction.INSTALLATION_EVENT_RECEIVED,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=metadata,
            immediate=True,
        )
        return result

    if action == "deleted":
        return await run_in_threadpool(_handle_installation_deleted, data)

    if action == "suspended":
        return await run_in_threadpool(_handle_installation_suspended, data)

    if action == "unsuspended":
        result = await run_in_threadpool(_handle_installation_unsuspended, data)
        schedule_task(_sync_installation_metadata, installation_id)
        return result

    return {
        "status": "ignored",
        "event": "installation",
        "action": action,
    }


async def _handle_installation_created(
    *,
    data: InstallationWebhookPayload,
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    result = await run_in_threadpool(
        _create_installation,
        data,
    )

    if result["status"] != "created":
        return result

    installation_id = int(result["installation_id"])
    await _register_knowledge_source(installation_id)
    schedule_task(_sync_installation_metadata, installation_id)

    return result


def _create_installation(
    data: InstallationWebhookPayload,
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
    except SyncAPIError as exc:
        logger.warning(
            "[GITHUB][WEBHOOK][INGRESS] Installation metadata sync failed: installation_id=%s, code=%s, message=%s, metadata=%s",
            installation_id,
            exc.code,
            exc.message,
            exc.metadata,
        )
    except Exception as exc:
        logger.error(
            "[GITHUB][WEBHOOK][INGRESS] Installation metadata sync failed: installation_id=%s, error=%s",
            installation_id,
            exc,
            exc_info=True,
        )


async def _register_knowledge_source(installation_id: int) -> None:
    def _sync_task() -> None:
        with SessionLocal() as db:
            workspace = get_workspace_limit_one(db)
            if not workspace:
                logger.error("[GITHUB][WEBHOOK][INGRESS] Workspace not found")
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
