from __future__ import annotations

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.webhook.resolver import resolve_jira_metadata_event
from catchup.connectors.jira.webhook.responses import ignored_event_response
from catchup.connectors.jira.webhook.responses import processed_metadata_response
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository
from catchup.sync.ingress.types import JiraWebhookRequest
from catchup.sync.ingress.types import JiraWebhookResponse

logger = structlog.get_logger(__name__)


async def handle_metadata_event(
    request: JiraWebhookRequest,
) -> JiraWebhookResponse:
    return await run_in_threadpool(
        _handle_metadata_event_db,
        request,
    )


def _handle_metadata_event_db(
    request: JiraWebhookRequest,
) -> JiraWebhookResponse:
    with SessionLocal() as db:
        try:
            response = _process_metadata_event(
                db=db,
                request=request,
            )
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise


def _process_metadata_event(
    *,
    db: Session,
    request: JiraWebhookRequest,
) -> JiraWebhookResponse:
    cloud_id = request.cloud_id
    event_type = request.event_type
    resolved = resolve_jira_metadata_event(
        event_type=event_type,
        payload=request.payload,
    )

    if resolved.action == "project_upsert":
        project = resolved.project or {}
        project_key = resolved.project_key
        if not project_key:
            raise ValueError("missing_project_key")

        project_id = str(project.get("id") or "")
        if not project_id:
            raise ValueError("missing_project_id")

        lead = project.get("lead") or {}
        domain_repository.upsert_project(
            db=db,
            cloud_id=cloud_id,
            project_key=project_key,
            project_id=project_id,
            project_name=project.get("name") or project_key,
            description=project.get("description"),
            project_type=project.get("projectTypeKey"),
            lead_account_id=lead.get("accountId"),
            lead_display_name=lead.get("displayName"),
            url=project.get("self"),
        )

        logger.info(
            "jira_project_upserted",
            cloud_id=cloud_id,
            project_key=project_key,
            event_type=event_type,
        )
        return processed_metadata_response(
            event_type=event_type,
            entity="project",
            key=project_key,
        )

    if resolved.action == "project_delete":
        project_key = resolved.project_key
        if not project_key:
            raise ValueError("missing_project_key")

        domain_repository.delete_project(db, cloud_id, project_key)
        logger.info(
            "jira_project_deleted",
            cloud_id=cloud_id,
            project_key=project_key,
        )
        return processed_metadata_response(
            event_type=event_type,
            entity="project",
            key=project_key,
        )

    if resolved.action == "sprint_upsert":
        sprint = resolved.sprint or {}
        sprint_id = sprint.get("id")
        sprint_name = sprint.get("name")
        if sprint_id is None or not sprint_name:
            raise ValueError("missing_sprint_id_or_name")

        domain_repository.upsert_sprint(
            db=db,
            cloud_id=cloud_id,
            sprint_id=int(sprint_id),
            sprint_name=sprint_name,
            state=sprint.get("state"),
            goal=sprint.get("goal"),
            project_key=resolved.project_key,
            board_id=sprint.get("originBoardId"),
            start_date=parse_atlassian_datetime(sprint.get("startDate")),
            end_date=parse_atlassian_datetime(sprint.get("endDate")),
            complete_date=parse_atlassian_datetime(sprint.get("completeDate")),
        )

        logger.info(
            "jira_sprint_upserted",
            cloud_id=cloud_id,
            sprint_id=sprint_id,
            event_type=event_type,
        )
        return processed_metadata_response(
            event_type=event_type,
            entity="sprint",
            entity_id=int(sprint_id),
        )

    if resolved.action == "sprint_delete":
        sprint = resolved.sprint or {}
        sprint_id = sprint.get("id")
        if sprint_id is None:
            raise ValueError("missing_sprint_id")

        domain_repository.delete_sprint(db, cloud_id, int(sprint_id))
        logger.info(
            "jira_sprint_deleted",
            cloud_id=cloud_id,
            sprint_id=sprint_id,
        )
        return processed_metadata_response(
            event_type=event_type,
            entity="sprint",
            entity_id=int(sprint_id),
        )

    if resolved.action == "user_upsert":
        user = resolved.user or {}
        account_id = user.get("accountId")
        if not account_id:
            raise ValueError("missing_account_id")

        avatar_urls = user.get("avatarUrls") or {}
        domain_repository.upsert_user(
            db=db,
            cloud_id=cloud_id,
            account_id=account_id,
            display_name=user.get("displayName") or "Unknown",
            account_type=user.get("accountType") or "atlassian",
            active=user.get("active", True),
            email_address=user.get("emailAddress"),
            avatar_url=avatar_urls.get("48x48"),
            self_url=user.get("self"),
        )

        logger.info(
            "jira_user_upserted",
            cloud_id=cloud_id,
            account_id=account_id,
            event_type=event_type,
        )
        return processed_metadata_response(
            event_type=event_type,
            entity="user",
            entity_id=account_id,
        )

    if resolved.action == "user_delete":
        user = resolved.user or {}
        account_id = user.get("accountId")
        if not account_id:
            raise ValueError("missing_account_id")

        domain_repository.delete_user(db, cloud_id, account_id)
        logger.info(
            "jira_user_deleted",
            cloud_id=cloud_id,
            account_id=account_id,
        )
        return processed_metadata_response(
            event_type=event_type,
            entity="user",
            entity_id=account_id,
        )

    return ignored_event_response(
        event_type=event_type,
        reason=resolved.ignored_reason or "unsupported_event",
    )
