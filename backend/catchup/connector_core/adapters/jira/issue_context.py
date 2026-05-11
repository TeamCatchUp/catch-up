from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.connector_core.adapters.jira.issue_dependencies import (
    JiraIssueIngestionDependencies,
)
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities


async def prepare_jira_issue_transform_context(
    *,
    dependencies: JiraIssueIngestionDependencies,
    project_key: str,
) -> None:
    def load_project_cache():
        with SessionLocal() as db:
            return jira_entities.get_projects_by_keys(
                db,
                dependencies.cloud_id,
                [project_key],
            )

    project_cache = await run_in_threadpool(
        load_project_cache,
    )
    dependencies.transformer.project_cache = project_cache
