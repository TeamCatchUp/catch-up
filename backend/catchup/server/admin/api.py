import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.db.dependencies import get_db
from catchup.db.models import (
    AtlassianOAuthToken,
    GithubInstallation,
    GithubRepository,
    GithubSyncState,
    JiraProject,
    JiraSyncState,
    SlackChannelSyncState,
    SlackOAuthToken,
    SlackSyncState,
    User,
)
from catchup.server.auth.schemas import (
    GithubConnectorStatus,
    JiraConnectorStatus,
    SlackConnectorStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def _format_date(dt):
    if not dt:
        return None
    try:
        return dt.date().isoformat()
    except Exception:
        return None


def _get_github_status(db: Session) -> GithubConnectorStatus:
    installation_ids = [
        row[0] for row in db.query(GithubInstallation.installation_id).all()
    ]

    if not installation_ids:
        logger.info("[JIRA][FULL SYNC] Github connector status: no installation found")
        return GithubConnectorStatus(
            connected=False,
            oldest=None,
            latest=None,
            repositories=[],
        )

    repositories = [
        row[0]
        for row in db.query(GithubRepository.full_name)
        .filter(GithubRepository.installation_id.in_(installation_ids))
        .all()
    ]

    latest_dt = (
        db.query(func.max(GithubSyncState.last_successful_sync_at))
        .filter(GithubSyncState.installation_id.in_(installation_ids))
        .scalar()
    )

    oldest_dt = None
    try:
        sql = text(
            """
            SELECT MIN(
                COALESCE(
                    cmetadata ->> 'created_at',
                    cmetadata ->> 'committed_at',
                    cmetadata ->> 'merged_at',
                    cmetadata ->> 'closed_at',
                    cmetadata ->> 'synced_at'
                )::timestamptz
            ) AS oldest
            FROM langchain_pg_embedding
            WHERE cmetadata ->> 'source' = 'github'
            """
        )
        result = db.execute(sql).first()
        oldest_dt = result[0] if result and result[0] else None
    except Exception as e:
        logger.warning(
            "[JIRA][FULL SYNC] Failed to fetch github oldest embedding date: %s", e
        )

    return GithubConnectorStatus(
        connected=True,
        oldest=_format_date(oldest_dt),
        latest=_format_date(latest_dt),
        repositories=repositories,
    )


@router.get(
    path="/connector/github/status",
    description="Github 연동 상태 조회 (admin 전용)",
    response_model=GithubConnectorStatus,
)
def get_github_connector_status(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    return _get_github_status(db)


def _get_jira_status(db: Session) -> JiraConnectorStatus:
    # Atlassian OAuth 토큰이 있으면 Jira 연동됨으로 판단 (공용 토큰)
    cloud_ids = [row[0] for row in db.query(AtlassianOAuthToken.cloud_id).all()]

    if not cloud_ids:
        logger.info("[JIRA][FULL SYNC] Jira connector status: no oauth token found")
        return JiraConnectorStatus(
            connected=False,
            oldest=None,
            latest=None,
            projects=[],
        )

    projects = [
        f"{row.project_key}:{row.project_name}"
        for row in db.query(JiraProject.project_key, JiraProject.project_name)
        .filter(JiraProject.cloud_id.in_(cloud_ids))
        .all()
    ]

    latest_dt = (
        db.query(func.max(JiraSyncState.last_successful_sync_at))
        .filter(JiraSyncState.cloud_id.in_(cloud_ids))
        .scalar()
    )

    oldest_dt = None
    try:
        sql = text(
            """
            SELECT MIN(
                COALESCE(
                    cmetadata ->> 'created_at',
                    cmetadata ->> 'updated_at',
                    cmetadata ->> 'resolved_at',
                    cmetadata ->> 'synced_at'
                )::timestamptz
            ) AS oldest
            FROM langchain_pg_embedding
            WHERE cmetadata ->> 'source' = 'jira'
            """
        )
        result = db.execute(sql).first()
        oldest_dt = result[0] if result and result[0] else None
    except Exception as e:
        logger.warning(
            "[JIRA][FULL SYNC] Failed to fetch jira oldest embedding date: %s", e
        )

    return JiraConnectorStatus(
        connected=True,
        oldest=_format_date(oldest_dt),
        latest=_format_date(latest_dt),
        projects=projects,
    )


@router.get(
    path="/connector/jira/status",
    description="Jira 연동 상태 조회 (admin 전용)",
    response_model=JiraConnectorStatus,
)
def get_jira_connector_status(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    return _get_jira_status(db)


def _get_slack_status(db: Session) -> SlackConnectorStatus:
    team_ids = [row[0] for row in db.query(SlackOAuthToken.team_id).all()]

    if not team_ids:
        logger.info("[SLACK][FULL SYNC] Slack connector status: no oauth token found")
        return SlackConnectorStatus(
            connected=False,
            oldest=None,
            latest=None,
            channels=[],
        )

    channels = [
        row[0]
        for row in db.query(SlackChannelSyncState.channel_name)
        .filter(SlackChannelSyncState.team_id.in_(team_ids))
        .distinct()
        .all()
        if row[0]
    ]

    latest_dt = (
        db.query(func.max(SlackSyncState.last_successful_sync_at))
        .filter(SlackSyncState.team_id.in_(team_ids))
        .scalar()
    )

    oldest_dt = None
    try:
        sql = text(
            """
            SELECT MIN(
                COALESCE(
                    cmetadata ->> 'created_at',
                    cmetadata ->> 'updated_at',
                    cmetadata ->> 'synced_at'
                )::timestamptz
            ) AS oldest
            FROM langchain_pg_embedding
            WHERE cmetadata ->> 'source' = 'slack'
            """
        )
        result = db.execute(sql).first()
        oldest_dt = result[0] if result and result[0] else None
    except Exception as e:
        logger.warning(
            "[SLACK][FULL SYNC] Failed to fetch slack oldest embedding date: %s", e
        )

    return SlackConnectorStatus(
        connected=True,
        oldest=_format_date(oldest_dt),
        latest=_format_date(latest_dt),
        channels=channels,
    )


@router.get(
    path="/connector/slack/status",
    description="Slack 연동 상태 조회 (admin 전용)",
    response_model=SlackConnectorStatus,
)
def get_slack_connector_status(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    return _get_slack_status(db)
