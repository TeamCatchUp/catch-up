from __future__ import annotations

from typing import Any

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.jira.client import JiraApiClient
from catchup.db.atlassian import oauth_repository as atlassian_oauth_repository
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities
from catchup.db.models import AtlassianOAuthToken
from catchup.db.models import SyncConnector
from catchup.sync.query.providers.common import build_targets_result
from catchup.sync.query.types import SyncTargetResult
from catchup.sync.query.types import SyncTargetsResult


def _load_jira_token_db(scope_id: str) -> AtlassianOAuthToken | None:
    with SessionLocal() as db:
        return atlassian_oauth_repository.get_token_by_cloud_id(db, scope_id)


def _persist_jira_projects_db(
    cloud_id: str,
    projects: list[dict[str, Any]],
) -> None:
    with SessionLocal() as db:
        try:
            jira_entities.sync_projects_snapshot(
                db,
                cloud_id,
                projects,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


async def list_jira_targets(*, scope_id: str) -> SyncTargetsResult:
    token = await run_in_threadpool(_load_jira_token_db, scope_id)
    if token is None:
        raise ValueError(f"jira cloud is not connected: {scope_id}")

    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=atlassian_oauth_repository,
    )
    client = JiraApiClient(
        scope_id,
        AtlassianTokenProvider(token_manager),
    )
    raw_projects = await client.get_all_projects()
    site_url = (token.site_url or "").rstrip("/")

    project_rows: list[dict[str, Any]] = []
    targets: list[SyncTargetResult] = []
    for raw_project in raw_projects:
        project_key = str(raw_project.get("key") or "").strip()
        if not project_key:
            continue

        project_id = str(raw_project.get("id") or "")
        project_name = str(raw_project.get("name") or project_key).strip() or project_key
        lead = raw_project.get("lead")
        lead_data = lead if isinstance(lead, dict) else {}

        project_rows.append(
            {
                "cloud_id": scope_id,
                "project_key": project_key,
                "project_id": project_id,
                "project_name": project_name,
                "description": raw_project.get("description"),
                "project_type": raw_project.get("projectTypeKey"),
                "lead_account_id": lead_data.get("accountId"),
                "lead_display_name": lead_data.get("displayName"),
                "url": f"{site_url}/projects/{project_key}" if site_url else None,
            }
        )
        targets.append(
            SyncTargetResult(
                target_id=project_key,
                display_name=project_name,
                target_type="project",
                is_accessible=True,
                metadata={
                    "project_key": project_key,
                    "project_id": project_id,
                },
            )
        )

    targets.sort(key=lambda item: item.target_id)
    await run_in_threadpool(
        _persist_jira_projects_db,
        scope_id,
        project_rows,
    )
    return build_targets_result(
        connector=SyncConnector.JIRA,
        scope_id=scope_id,
        targets=targets,
    )
