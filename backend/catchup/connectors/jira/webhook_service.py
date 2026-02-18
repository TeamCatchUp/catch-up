import logging

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.db.jira import domain_repository

logger = logging.getLogger(__name__)

SUPPORTED_METADATA_EVENTS = {
    "jira:project_created",
    "jira:project_updated",
    "jira:project_deleted",
    "sprint_created",
    "sprint_updated",
    "sprint_deleted",
    "user_created",
    "user_updated",
    "user_deleted",
}

def _extract_project_key(payload: dict) -> str | None:
    project = payload.get("project") or {}
    return project.get("key") or payload.get("projectKey")

def _extract_user(payload: dict) -> dict:
    return payload.get("user") or payload.get("account") or {}


def handle_metadata_event(
        db: Session,
        cloud_id: str,
        event_type: str,
        payload: dict,
) -> dict:
    
    if event_type in {"jira:project_created", "jira:project_updated"}:
        project = payload.get("project") or {}
        project_key = project.get("key")
        if not project_key:
            raise ValueError("missing_project_key")
        
        project_id = str(project.get("id") or "")
        project_name = project.get("name") or project_key
        if not project_id:
            raise ValueError("missing_project_id")
        
        lead = project.get("lead") or {}

        domain_repository.upsert_project(
            db=db,
            cloud_id=cloud_id,
            project_key=project_key,
            project_id=project_id,
            project_name=project_name,
            description=project.get("description"),
            project_type=project.get("projectTypeKey"),
            lead_account_id=lead.get("accountId"),
            lead_display_name=lead.get("displayName"),
            url=project.get("self"),
        )

        logger.info(
            f"[JIRA][WEBHOOK] Project upserted: "
            f"cloud_id={cloud_id}, project_key={project_key}, event_type={event_type}"
        )
        return {"status": "processed", "event_type": event_type, "entity": "project", "key": project_key}

    if event_type == "jira:project_deleted":
        project_key = _extract_project_key(payload)
        if not project_key:
            raise ValueError("missing_project_key")
        
        domain_repository.delete_project(db, cloud_id, project_key)

        logger.info(
            f"[JIRA][WEBHOOK] Project Deleted: cloud_id={cloud_id}, project_key={project_key}"
        )

        return {"status": "processed", "event_type": event_type, "entity": "project", "key": project_key}
    
    if event_type in {"sprint_created", "sprint_updated"}:
        sprint = payload.get("sprint") or {}
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
            project_key=_extract_project_key(payload),
            board_id=sprint.get("originBoardId"),
            start_date=parse_atlassian_datetime(sprint.get("startDate")),
            end_date=parse_atlassian_datetime(sprint.get("endDate")),
            complete_date=parse_atlassian_datetime(sprint.get("completeDate")),
        )

        logger.info(
            f"[JIRA][WEBHOOK][METADATA] Sprint upserted: "
            f"cloud_id={cloud_id}, sprint_id={sprint_id}, event_type={event_type}"
        )
        return {"status": "processed", "event_type": event_type, "entity": "sprint", "id": int(sprint_id)}

    if event_type == "sprint_deleted":
        sprint = payload.get("sprint") or {}
        sprint_id = sprint.get("id")
        if sprint_id is None:
            raise ValueError("missing_sprint_id")

        domain_repository.delete_sprint(db, cloud_id, int(sprint_id))

        logger.info(
            f"[JIRA][WEBHOOK][METADATA] Sprint deleted: "
            f"cloud_id={cloud_id}, sprint_id={sprint_id}"
        )
        return {"status": "processed", "event_type": event_type, "entity": "sprint", "id": int(sprint_id)}

    if event_type in {"user_created", "user_updated"}:
        user = _extract_user(payload)
        account_id = user.get("accountId")
        display_name = user.get("displayName") or "Unknown"

        if not account_id:
            raise ValueError("missing_account_id")

        avatar_urls = user.get("avatarUrls") or {}

        domain_repository.upsert_user(
            db=db,
            cloud_id=cloud_id,
            account_id=account_id,
            display_name=display_name,
            account_type=user.get("accountType") or "atlassian",
            active=user.get("active", True),
            email_address=user.get("emailAddress"),
            avatar_url=avatar_urls.get("48x48"),
            self_url=user.get("self"),
        )

        logger.info(
            f"[JIRA][WEBHOOK][METADATA] User upserted: "
            f"cloud_id={cloud_id}, account_id={account_id}, event_type={event_type}"
        )
        return {"status": "processed", "event_type": event_type, "entity": "user", "id": account_id}

    if event_type == "user_deleted":
        user = _extract_user(payload)
        account_id = user.get("accountId")
        if not account_id:
            raise ValueError("missing_account_id")

        domain_repository.delete_user(db, cloud_id, account_id)

        logger.info(
            f"[JIRA][WEBHOOK][METADATA] User deleted: "
            f"cloud_id={cloud_id}, account_id={account_id}"
        )
        return {"status": "processed", "event_type": event_type, "entity": "user", "id": account_id}

    return {"status": "ignored", "event_type": event_type}
