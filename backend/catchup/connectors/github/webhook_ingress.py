from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    SyncConnector,
)
from catchup.db.workspaces import get_workspace_limit_one
from catchup.sync.incremental import ingest_record_changes
from catchup.sync.incremental.schemas import RecordChange

logger = logging.getLogger(__name__)

ScheduleTask = Callable[..., None]

_INCREMENTAL_EVENTS = frozenset({
    "issues",
    "issue_comment",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "pull_request_review_thread",
})

_METADATA_EVENTS = frozenset({
    "installation",
    "installation_repositories",
    "repository",
    "organization",
    "membership",
    "member",
})

_REPOSITORY_REFRESH_EVENTS = frozenset({
    "repository",
})

_USER_REFRESH_EVENTS = frozenset({
    "organization",
    "membership",
    "member",
})


async def handle_webhook(
    *,
    db: Session,
    event_name: str | None,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    normalized_event = str(event_name or "").strip().lower()

    if normalized_event == "ping":
        return {"status": "ignored", "event": normalized_event, "reason": "handshake"}

    if normalized_event in _INCREMENTAL_EVENTS:
        return _handle_incremental_event(
            db=db,
            event_name=normalized_event,
            payload=payload,
        )

    if normalized_event in _METADATA_EVENTS:
        return await _handle_metadata_event(
            db=db,
            event_name=normalized_event,
            payload=payload,
            schedule_task=schedule_task,
        )

    return {"status": "ignored", "event": normalized_event, "reason": "unsupported_event"}


def _handle_incremental_event(
    *,
    db: Session,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # comment/review 계열도 별도 child record를 만들지 않고 부모 Issue/PR를 다시 sync한다.
    changes = _build_incremental_changes(
        event_name=event_name,
        payload=payload,
    )
    if not changes:
        return {"status": "ignored", "event": event_name, "reason": "unsupported_payload"}

    record_keys = ingest_record_changes(db, changes)
    return {"status": "accepted", "event": event_name, "record_keys": record_keys}


async def _handle_metadata_event(
    *,
    db: Session,
    event_name: str,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    if event_name == "installation":
        return await _handle_installation_event(
            db=db,
            payload=payload,
            schedule_task=schedule_task,
        )

    if event_name == "installation_repositories":
        return _handle_installation_repositories_event(
            db=db,
            payload=payload,
        )

    installation_id = _extract_installation_id(payload)
    if installation_id is None:
        return {
            "status": "ignored",
            "event": event_name,
            "reason": "missing_installation_id",
        }

    logger.info(
        "[GITHUB][WEBHOOK][INGRESS] Metadata refresh scheduled: event=%s, installation_id=%s",
        event_name,
        installation_id,
    )
    schedule_task(_sync_installation_metadata, installation_id)

    refresh_target = "repositories" if event_name in _REPOSITORY_REFRESH_EVENTS else "users"
    if event_name not in _REPOSITORY_REFRESH_EVENTS | _USER_REFRESH_EVENTS:
        refresh_target = "metadata"

    return {
        "status": "processed",
        "event": event_name,
        "refresh_target": refresh_target,
        "installation_id": installation_id,
    }


def _build_incremental_changes(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> list[RecordChange]:
    installation_id = _extract_installation_id(payload)
    repository_id = _extract_repository_id(payload)
    if installation_id is None or repository_id is None:
        return []

    record_type, record_id, last_event_at = _resolve_parent_record(event_name, payload)
    if not record_type or not record_id:
        return []

    return [
        RecordChange(
            connector=SyncConnector.GITHUB,
            scope_id=str(installation_id),
            record_type=record_type,
            record_id=record_id,
            parent_type="repository",
            parent_id=str(repository_id),
            event_kind=_resolve_event_kind(event_name, payload),
            last_event_at=last_event_at,
        )
    ]


def _resolve_parent_record(
    event_name: str,
    payload: dict[str, Any],
) -> tuple[str, str, datetime]:
    if event_name == "issues":
        issue = payload.get("issue") or {}
        return (
            "issue",
            str(issue.get("number") or "").strip(),
            _parse_datetime(issue.get("updated_at"))
            or _parse_datetime(issue.get("created_at"))
            or _utc_now(),
        )

    if event_name == "issue_comment":
        issue = payload.get("issue") or {}
        comment = payload.get("comment") or {}
        # issue_comment 는 comment 자체가 아니라 부모 Issue/PR 문서를 다시 sync한다.
        record_type = "pull_request" if issue.get("pull_request") else "issue"
        return (
            record_type,
            str(issue.get("number") or "").strip(),
            _parse_datetime(comment.get("updated_at"))
            or _parse_datetime(comment.get("created_at"))
            or _parse_datetime(issue.get("updated_at"))
            or _utc_now(),
        )

    if event_name == "pull_request":
        pull_request = payload.get("pull_request") or {}
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(pull_request.get("updated_at"))
            or _parse_datetime(pull_request.get("created_at"))
            or _utc_now(),
        )

    if event_name == "pull_request_review":
        pull_request = payload.get("pull_request") or {}
        review = payload.get("review") or {}
        # review 이벤트도 부모 PR 문서를 다시 sync한다.
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(review.get("submitted_at"))
            or _parse_datetime(review.get("submittedAt"))
            or _parse_datetime(pull_request.get("updated_at"))
            or _utc_now(),
        )

    if event_name == "pull_request_review_comment":
        pull_request = payload.get("pull_request") or {}
        comment = payload.get("comment") or {}
        # review comment 이벤트도 부모 PR 문서를 다시 sync한다.
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(comment.get("updated_at"))
            or _parse_datetime(comment.get("created_at"))
            or _parse_datetime(pull_request.get("updated_at"))
            or _utc_now(),
        )

    if event_name == "pull_request_review_thread":
        pull_request = payload.get("pull_request") or {}
        thread = payload.get("thread") or {}
        # review thread 이벤트도 부모 PR 문서를 다시 sync한다.
        return (
            "pull_request",
            str(pull_request.get("number") or "").strip(),
            _parse_datetime(thread.get("updated_at"))
            or _parse_datetime(thread.get("created_at"))
            or _parse_datetime(pull_request.get("updated_at"))
            or _utc_now(),
        )

    return "", "", _utc_now()


def _resolve_event_kind(
    event_name: str,
    payload: dict[str, Any],
) -> str:
    if event_name in {
        "issue_comment",
        "pull_request_review",
        "pull_request_review_comment",
        "pull_request_review_thread",
    }:
        return "updated"

    action = str(payload.get("action") or "").strip().lower()
    if action in {"opened", "reopened"}:
        return "created"
    if action == "deleted":
        return "deleted"
    return "updated"


async def _handle_installation_event(
    *,
    db: Session,
    payload: dict[str, Any],
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    data = InstallationWebhookPayload(**payload)
    action = data.action

    if action == "created":
        return await _handle_installation_created(
            db=db,
            data=data,
            schedule_task=schedule_task,
        )

    if action == "deleted":
        return _handle_installation_deleted(
            db=db,
            data=data,
        )

    if action == "suspended":
        return _handle_installation_suspended(
            db=db,
            data=data,
        )

    if action == "unsuspended":
        return _handle_installation_unsuspended(
            db=db,
            data=data,
            schedule_task=schedule_task,
        )

    return {"status": "ignored", "event": "installation", "action": action}


async def _handle_installation_created(
    *,
    db: Session,
    data: InstallationWebhookPayload,
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    installation = data.installation

    existing = installation_crud.get_installation_by_installation_id(db, installation.id)
    if existing:
        return {"status": "exists", "installation_id": installation.id}

    account = installation.account
    repository_selection = None
    if installation.repository_selection:
        repository_selection = GithubRepositorySelection(installation.repository_selection)

    created = installation_crud.create_installation(
        db=db,
        installation_id=installation.id,
        account_type=GithubInstallationType(account.type.lower()),
        account_id=account.id,
        account_login=account.login,
        account_avatar_url=account.avatar_url,
        repository_selection=repository_selection,
        suspended_at=installation.suspended_at,
    )

    await _register_knowledge_source(installation.id)
    schedule_task(_sync_installation_metadata, installation.id)

    return {
        "status": "created",
        "installation_id": created.installation_id,
    }


def _handle_installation_deleted(
    *,
    db: Session,
    data: InstallationWebhookPayload,
) -> dict[str, Any]:
    installation_id = data.installation.id

    github_entities.delete_installation_repositories(db, installation_id)
    deleted = installation_crud.delete_installation_by_installation_id(db, installation_id)

    if deleted:
        return {"status": "deleted", "installation_id": installation_id}

    return {"status": "not_found", "installation_id": installation_id}


def _handle_installation_suspended(
    *,
    db: Session,
    data: InstallationWebhookPayload,
) -> dict[str, Any]:
    installation = data.installation
    installation_crud.update_installation_suspended(db, installation.id, installation.suspended_at)
    return {"status": "suspended", "installation_id": installation.id}


def _handle_installation_unsuspended(
    *,
    db: Session,
    data: InstallationWebhookPayload,
    schedule_task: ScheduleTask,
) -> dict[str, Any]:
    installation_id = data.installation.id
    installation_crud.update_installation_suspended(db, installation_id, None)
    schedule_task(_sync_installation_metadata, installation_id)
    return {"status": "unsuspended", "installation_id": installation_id}


def _handle_installation_repositories_event(
    *,
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = InstallationRepositoriesWebhookPayload(**payload)
    installation_id = data.installation.id

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

    return {
        "status": "processed",
        "event": "installation_repositories",
        "installation_id": installation_id,
        "added": len(data.repositories_added),
        "removed": len(data.repositories_removed),
    }


async def _sync_installation_metadata(installation_id: int) -> None:
    try:
        with SessionLocal() as db:
            service = await create_github_ingestion_service(db, installation_id)
            await service.sync_installation_metadata(db)
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


def _extract_repository_id(payload: dict[str, Any]) -> int | None:
    repository = payload.get("repository") or {}
    raw = repository.get("id")
    if raw in (None, ""):
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
