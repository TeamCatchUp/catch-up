from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.sync.ingestion.adapters.github.repository_models import GithubRepoRef


class GithubRepositoryRefResolver:
    """Resolve stored GitHub repository ids into owner/repo references."""

    def __init__(self, installation_id: int) -> None:
        self._installation_id = installation_id

    async def get_repo_ref(self, repo_id: int) -> GithubRepoRef:
        return await asyncio.to_thread(self.load_repo_ref_sync, repo_id)

    def load_repo_ref_sync(self, repo_id: int) -> GithubRepoRef:
        with SessionLocal() as db:
            repo_names = self.get_repo_names_by_ids(db, [repo_id])

        if not repo_names:
            raise ValueError(f"github repository not found: repo_id={repo_id}")

        full_name = repo_names[0]
        owner, repo = full_name.split("/", 1)
        return GithubRepoRef(
            repo_id=repo_id,
            full_name=full_name,
            owner=owner,
            repo=repo,
        )

    def get_repo_names_by_ids(self, db: Session, repo_ids: list[int]) -> list[str]:
        repos = github_entities.get_repositories_by_installation(
            db,
            self._installation_id,
        )
        repo_id_set = set(repo_ids)
        return [repo.full_name for repo in repos if repo.repo_id in repo_id_set]
