import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.db.dependencies import get_db
from catchup.db.models import (
    AtlassianOAuthToken,
    ConfluenceSpace,
    ConfluenceSyncState,
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
    ConfluenceSyncableResponse,
    ConfluenceConnectorStatus,
    ConfluenceSyncableSpace,
    GithubConnectorStatus,
    GithubSyncableRepository,
    GithubSyncableResponse,
    JiraConnectorStatus,
    JiraSyncableProject,
    JiraSyncableResponse,
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


def _get_confluence_status(db: Session) -> ConfluenceConnectorStatus:
    # Jira와 동일한 AtlassianOAuthToken 사용 (공용 토큰)
    cloud_ids = [row[0] for row in db.query(AtlassianOAuthToken.cloud_id).all()]

    if not cloud_ids:
        logger.info("[CONFLUENCE][FULL SYNC] Confluence connector status: no oauth token found")
        return ConfluenceConnectorStatus(
            connected=False,
            oldest=None,
            latest=None,
            spaces=[],
        )

    # Sync 이력이 있는 Space만 조회
    spaces = [
        row[0]
        for row in db.query(ConfluenceSyncState.space_key)
        .filter(ConfluenceSyncState.cloud_id.in_(cloud_ids))
        .distinct()
        .all()
    ]

    latest_dt = (
        db.query(func.max(ConfluenceSyncState.last_successful_sync_at))
        .filter(ConfluenceSyncState.cloud_id.in_(cloud_ids))
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
            WHERE cmetadata ->> 'source' = 'confluence'
            """
        )
        result = db.execute(sql).first()
        oldest_dt = result[0] if result and result[0] else None
    except Exception as e:
        logger.warning(
            "[CONFLUENCE][FULL SYNC] Failed to fetch confluence oldest embedding date: %s", e
        )

    return ConfluenceConnectorStatus(
        connected=True,
        oldest=_format_date(oldest_dt),
        latest=_format_date(latest_dt),
        spaces=spaces,
    )


@router.get(
    path="/connector/confluence/status",
    description="Confluence 연동 상태 조회 (admin 전용)",
    response_model=ConfluenceConnectorStatus,
)
def get_confluence_connector_status(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    return _get_confluence_status(db)


def _get_syncable_jira_projects(db: Session) -> JiraSyncableResponse:
    rows = (
        db.query(JiraProject.cloud_id, JiraProject.project_key, JiraProject.project_name)
        .order_by(JiraProject.cloud_id, JiraProject.project_key)
        .all()
    )

    if not rows:
        logger.info("[ADMIN][SYNCABLE] Jira syncable projects not found")
        return {}

    projects: JiraSyncableResponse = {}
    # cloud_id별로 프로젝트 정보를 묶어서 정리
    for cloud_id, project_key, project_name in rows:
        projects.setdefault(cloud_id, []).append(
            JiraSyncableProject(project_key=project_key, project_name=project_name)
        )
    return projects


def _get_syncable_github_repositories(db: Session) -> GithubSyncableResponse:
    rows = (
        db.query(
            GithubRepository.installation_id,
            GithubRepository.full_name,
            GithubRepository.repo_id,
        )
        .order_by(GithubRepository.installation_id, GithubRepository.full_name)
        .all()
    )

    if not rows:
        logger.info("[ADMIN][SYNCABLE] Github syncable repositories not found")
        return {}

    repositories: GithubSyncableResponse = {}
    # installation_id별로 repository 정보를 묶어서 정리
    for installation_id, full_name, repo_id in rows:
        repositories.setdefault(str(installation_id), []).append(
            GithubSyncableRepository(full_name=full_name, repo_id=repo_id)
        )
    return repositories


def _get_syncable_confluence_spaces(db: Session) -> ConfluenceSyncableResponse:
    rows = (
        db.query(
            ConfluenceSpace.cloud_id,
            ConfluenceSpace.space_name,
            ConfluenceSpace.space_key,
        )
        .order_by(ConfluenceSpace.cloud_id, ConfluenceSpace.space_key)
        .all()
    )

    if not rows:
        logger.info("[ADMIN][SYNCABLE] Confluence syncable spaces not found")
        return {}

    spaces: ConfluenceSyncableResponse = {}
    # cloud_id별로 space 정보를 묶어서 정리
    for cloud_id, space_name, space_key in rows:
        spaces.setdefault(cloud_id, []).append(
            ConfluenceSyncableSpace(space_name=space_name, space_key=space_key)
        )
    return spaces


@router.get(
    path="/connector/syncable/{source}",
    description="연동된 소스별 동기화 대상 목록 조회 (admin 전용)",
    response_model=(
        JiraSyncableResponse | GithubSyncableResponse | ConfluenceSyncableResponse
    ),
)
def get_syncable_entities(
    source: str,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    normalized_source = source.lower()

    if normalized_source == "jira":
        return _get_syncable_jira_projects(db)
    if normalized_source == "github":
        return _get_syncable_github_repositories(db)
    if normalized_source == "confluence":
        return _get_syncable_confluence_spaces(db)

    logger.info("[ADMIN][SYNCABLE] Unsupported source requested: %s", source)
    raise HTTPException(
        status_code=400,
        detail="source must be one of: jira, github, confluence",
    )
