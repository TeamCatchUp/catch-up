from __future__ import annotations

from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.connector_core.adapters.jira.issue_dependencies import (
    JiraIssueIngestionDependencies,
)
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities


def _load_jira_issue_transform_context_db(
    *,
    cloud_id: str,
    project_key: str,
) -> tuple[dict[str, Any], dict[int, Any]]:
    with SessionLocal() as db:
        project_cache = jira_entities.get_projects_by_keys(
            db,
            cloud_id,
            [project_key],
        )
        sprints = jira_entities.get_sprints_by_cloud_id(db, cloud_id)
        sprint_cache = {sprint.sprint_id: sprint for sprint in sprints}
        return project_cache, sprint_cache


async def prepare_jira_issue_transform_context(
    *,
    dependencies: JiraIssueIngestionDependencies,
    project_key: str,
) -> None:
    project_cache, sprint_cache = await run_in_threadpool(
        _load_jira_issue_transform_context_db,
        cloud_id=dependencies.cloud_id,
        project_key=project_key,
    )
    dependencies.transformer.project_cache = project_cache
    dependencies.transformer.sprint_cache = sprint_cache
