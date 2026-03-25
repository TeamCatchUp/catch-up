from __future__ import annotations

from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.client import GitHubApiClient
from catchup.connectors.github.service import _convert_repos_to_dto
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import (
    get_installation_by_installation_id,
)
from catchup.db.models import SyncConnector
from catchup.sync.query.providers.common import build_targets_result
from catchup.sync.query.types import SyncTargetResult
from catchup.sync.query.types import SyncTargetsResult


def _load_github_installation_db(installation_id: int):
    with SessionLocal() as db:
        return get_installation_by_installation_id(db, installation_id)


def _persist_github_repositories_db(
    installation_id: int,
    repositories: list[Any],
) -> None:
    with SessionLocal() as db:
        try:
            github_entities.sync_repositories_snapshot(
                db,
                installation_id,
                repositories,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


async def list_github_targets(*, scope_id: str) -> SyncTargetsResult:
    try:
        installation_id = int(scope_id)
    except ValueError as exc:
        raise ValueError(f"github installation not found: {scope_id}") from exc

    installation = await run_in_threadpool(
        _load_github_installation_db,
        installation_id,
    )
    if installation is None:
        raise ValueError(f"github installation not found: {scope_id}")

    access_token = await get_github_app_service().get_installation_access_token(
        installation_id,
    )
    client = GitHubApiClient(access_token)
    repositories = _convert_repos_to_dto(await client.list_installation_repos())
    await run_in_threadpool(
        _persist_github_repositories_db,
        installation_id,
        repositories,
    )

    targets = [
        SyncTargetResult(
            target_id=str(repo.repo_id),
            display_name=repo.full_name,
            target_type="repository",
            is_accessible=True,
            metadata={
                "repository_full_name": repo.full_name,
                "installation_id": str(installation_id),
            },
        )
        for repo in repositories
    ]
    return build_targets_result(
        connector=SyncConnector.GITHUB,
        scope_id=scope_id,
        targets=targets,
    )
