from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.jira.runtime import JiraRuntime
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities


class JiraContextStore:

    def __init__(self, runtime: JiraRuntime):
        self.runtime = runtime

    def _load_project_keys_db(self) -> list[str]:
        with SessionLocal() as db:
            projects = jira_entities.get_projects_by_cloud_id(db, self.runtime.cloud_id)
            return [project.project_key for project in projects]

    async def load_project_keys(self) -> list[str]:
        return await run_in_threadpool(self._load_project_keys_db)

    def _load_transformer_context_db(self) -> dict[int, Any]:
        with SessionLocal() as db:
            sprints = jira_entities.get_sprints_by_cloud_id(db, self.runtime.cloud_id)
            return {sprint.sprint_id: sprint for sprint in sprints}

    async def prepare_transformer_context(self) -> dict[int, Any]:
        sprint_cache = await run_in_threadpool(
            self._load_transformer_context_db,
        )
        self.runtime.transformer.sprint_cache = sprint_cache
        return sprint_cache
