from enum import StrEnum
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.orm import Session, aliased

from catchup.user.role_service import promote_user_to_admin as promote_user_to_admin_service
from catchup.auth.dependencies import require_admin_user
from catchup.chat.schemas import UserQueryWithSaveStatusResponse
from catchup.db.chat_room import get_all_queries_for_admin
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.models import (
    AtlassianOAuthToken,
    ConfluenceSpace,
    ConfluenceUser,
    GitHubUser,
    GithubInstallation,
    GithubRepository,
    InactiveUser,
    JiraAccountType,
    JiraProject,
    JiraUser,
    PreMappingBuffer,
    SlackOAuthToken,
    SyncConnector,
    SyncJob,
    SyncJobStatus,
    SyncType,
    SlackUser,
    SlackChannel,
    SourceType,
    User,
    UserStatus,
    UserRole,
)
from catchup.db.user_source_mapping import SOURCE_MAP
from catchup.db.users import get_all_oauth_users_for_admin, get_all_users_for_admin
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
from catchup.server.admin.schemas import (
    OAuthUserResponse,
    PreMappingBulkUpdateRequest,
    PreMappingInfo,
    SyncStatusCounts,
    ToolUserResponse,
    UserResponse,
    UserSyncMapping,
    UserSyncStatusResponse,
    SourceUserCount,
    AdminUserListResponse,
    AdminUserListItem,
    AdminUserDetailResponse,
    DeactivateUserRequest,
    DeactivateUserResponse,
    DeleteUserResponse,
    PromoteUserResponse,
    UserIntegrations,
    JiraAccount,
    GithubAccount,
    SlackAccount,
    ConfluenceAccount,
    ConfluenceCloudIdListResponse,
)
from catchup.server.schemas import BasePagination, calculate_skip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def _format_date(dt):
    if not dt:
        return None
    try:
        return dt.date().isoformat()
    except Exception:
        return None


def _latest_full_sync_succeeded_at(
    db: Session,
    *,
    connector: SyncConnector,
    scope_ids: list[str],
):
    if not scope_ids:
        return None

    return (
        db.query(func.max(SyncJob.succeeded_at))
        .filter(
            SyncJob.connector == connector,
            SyncJob.sync_type == SyncType.FULL,
            SyncJob.status == SyncJobStatus.SUCCESS,
            SyncJob.scope_id.in_(scope_ids),
        )
        .scalar()
    )


def _get_github_status(db: Session) -> GithubConnectorStatus:
    installation_ids = [
        row[0] for row in db.query(GithubInstallation.installation_id).all()
    ]

    if not installation_ids:
        logger.info("[GITHUB][FULL SYNC] Github connector status: no installation found")
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

    latest_dt = _latest_full_sync_succeeded_at(
        db,
        connector=SyncConnector.GITHUB,
        scope_ids=[str(installation_id) for installation_id in installation_ids],
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
            "[GITHUB][FULL SYNC] Failed to fetch github oldest embedding date: %s", e
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

    latest_dt = _latest_full_sync_succeeded_at(
        db,
        connector=SyncConnector.JIRA,
        scope_ids=cloud_ids,
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
        for row in db.query(SlackChannel.name)
        .filter(SlackChannel.team_id.in_(team_ids))
        .distinct()
        .all()
        if row[0]
    ]

    latest_dt = _latest_full_sync_succeeded_at(
        db,
        connector=SyncConnector.SLACK,
        scope_ids=team_ids,
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

    spaces = [
        f"{row[0]}:{row[1]}"
        for row in db.query(ConfluenceSpace.space_name, ConfluenceSpace.space_key)
        .filter(ConfluenceSpace.cloud_id.in_(cloud_ids))
        .distinct()
        .all()
        if row[0] and row[1]
    ]

    latest_dt = _latest_full_sync_succeeded_at(
        db,
        connector=SyncConnector.CONFLUENCE,
        scope_ids=cloud_ids,
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


# ============================
# Admin - User state change
# ============================
def _deactivate_user(
    db: Session,
    admin_user: User,
    user_id: int,
    reason: str,
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.info("[ADMIN][USER_DEACTIVATE] user not found (user_id=%s)", user_id)
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.ADMIN:
        logger.info(
            "[ADMIN][USER_DEACTIVATE] cannot deactivate admin user (user_id=%s)",
            user_id,
        )
        raise HTTPException(status_code=403, detail="Cannot deactivate admin user")

    if user.status == UserStatus.DELETED:
        logger.info(
            "[ADMIN][USER_DEACTIVATE] cannot deactivate deleted user (user_id=%s)",
            user_id,
        )
        raise HTTPException(status_code=409, detail="User already deleted")

    if user.status == UserStatus.INACTIVE:
        logger.info(
            "[ADMIN][USER_DEACTIVATE] already inactive (user_id=%s)", user_id
        )
        raise HTTPException(status_code=409, detail="User already inactive")

    inactive = InactiveUser(
        user_id=user.id,
        reason=reason,
        admin_id=admin_user.id,
    )

    user.status = UserStatus.INACTIVE
    db.add(inactive)
    db.commit()
    db.refresh(user)
    db.refresh(inactive)

    logger.info(
        "[ADMIN][USER_DEACTIVATE] action=deactivate user_id=%s admin_id=%s reason=%s",
        user_id,
        admin_user.id,
        reason,
    )

    return DeactivateUserResponse(
        userId=user.id,
        status=user.status,
        inactiveRecordId=inactive.id,
        deactivatedAt=inactive.deactivated_at.isoformat(),
        reason=inactive.reason,
    )


def _delete_user(db: Session, admin_user: User, user_id: int):
    # 비활성 로그 없이 상태만 DELETED로 전환한다.
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.info("[ADMIN][USER_DELETE] user not found (user_id=%s)", user_id)
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.ADMIN:
        logger.info("[ADMIN][USER_DELETE] cannot delete admin user (user_id=%s)", user_id)
        raise HTTPException(status_code=403, detail="Cannot delete admin user")

    if user.status == UserStatus.DELETED:
        logger.info("[ADMIN][USER_DELETE] already deleted (user_id=%s)", user_id)
        raise HTTPException(status_code=409, detail="User already deleted")

    # 기존 비활성화 기록은 삭제한다 (상태 삭제 시 남기지 않음).
    removed_logs = (
        db.query(InactiveUser)
        .filter(InactiveUser.user_id == user.id)
        .delete(synchronize_session=False)
    )

    user.status = UserStatus.DELETED
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "[ADMIN][USER_DELETE] action=delete user_id=%s admin_id=%s removed_inactive_logs=%s",
        user_id,
        admin_user.id,
        removed_logs,
    )

    return DeleteUserResponse(userId=user.id, status=user.status)

# ============================
# Admin - User management
# ============================
def _get_admin_user_list(db: Session) -> AdminUserListResponse:
    rows = (
        db.query(
            User.id,
            User.name,
            User.department,
            User.role,
            User.job_level,
            User.status,
        )
        .order_by(User.name)
        .all()
    )

    users = [
        AdminUserListItem(
            id=row.id,
            name=row.name,
            department=row.department,
            role=row.role,
            jobLevel=row.job_level,
            status=row.status,
        )
        for row in rows
    ]

    logger.info("[ADMIN][USER_LIST] fetched users (count=%d)", len(users))
    return AdminUserListResponse(total=len(users), users=users)


def _get_integration_accounts(
    db: Session,
    user_email: str,
) -> UserIntegrations:
    mappings = {
        m.source_type: m.external_user_identifier
        for m in db.query(PreMappingBuffer)
        .filter(PreMappingBuffer.email == user_email)
        .all()
    }

    jira = None
    if SourceType.JIRA in mappings:
        account_id = mappings[SourceType.JIRA]
        row = (
            db.query(JiraUser)
            .filter(JiraUser.account_id == account_id)
            .order_by(JiraUser.synced_at.desc())
            .first()
        )
        if row:
            jira = JiraAccount(
                accountId=row.account_id,
                name=row.display_name,
                email=row.email_address or None,
                avatarUrl=row.avatar_url,
            )

    github = None
    if SourceType.GITHUB in mappings:
        login = mappings[SourceType.GITHUB]
        row = (
            db.query(GitHubUser)
            .filter(GitHubUser.login == login)
            .first()
        )
        if row:
            github = GithubAccount(
                login=row.login,
                name=row.name,
                email=row.email or None,
                avatarUrl=row.avatar_url,
            )

    slack = None
    if SourceType.SLACK in mappings:
        user_key = mappings[SourceType.SLACK]
        row = (
            db.query(SlackUser)
            .filter(SlackUser.user_id == user_key)
            .order_by(SlackUser.synced_at.desc())
            .first()
        )
        if row:
            slack = SlackAccount(
                userId=row.user_id,
                name=row.display_name or row.real_name,
                email=row.email or None,
                avatarUrl=row.avatar_url,
            )

    confluence = None
    if SourceType.CONFLUENCE in mappings:
        account_id = mappings[SourceType.CONFLUENCE]
        row = (
            db.query(ConfluenceUser)
            .filter(ConfluenceUser.account_id == account_id)
            .order_by(ConfluenceUser.synced_at.desc())
            .first()
        )
        if row:
            confluence = ConfluenceAccount(
                accountId=row.account_id,
                name=row.display_name or row.public_name,
                email=row.email or None,
                avatarUrl=row.avatar_url,
            )

    return UserIntegrations(
        jira=jira,
        github=github,
        slack=slack,
        confluence=confluence,
    )


@router.get(
    path="/users",
    description="관리자용 사용자 목록 조회",
    response_model=AdminUserListResponse,
)
def get_admin_users(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    return _get_admin_user_list(db)


@router.get(
    path="/users/{user_id}/detail",
    description="관리자용 사용자 상세 조회",
    response_model=AdminUserDetailResponse,
)
def get_admin_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.info("[ADMIN][USER_DETAIL] user not found (user_id=%s)", user_id)
        raise HTTPException(status_code=404, detail="User not found")

    integrations = _get_integration_accounts(db, user.email)
    logger.info("[ADMIN][USER_DETAIL] fetched detail (user_id=%s)", user_id)

    return AdminUserDetailResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        department=user.department,
        jobLevel=user.job_level,
        status=user.status,
        integrations=integrations,
    )


# ============================
# User Sync Status (pre-mapping)
# ============================
def _get_user_sync_counts(db: Session) -> SyncStatusCounts:
    """협업 도구별 실제 사용자 수와 PreMappingBuffer 수를 집계한다."""
    jira_users = (
        db.query(func.count())
        .select_from(JiraUser)
        .filter(JiraUser.account_type == JiraAccountType.ATLASSIAN)
        .scalar()
    )
    slack_users = (
        db.query(func.count())
        .select_from(SlackUser)
        .filter(SlackUser.is_bot == False)  # noqa: E712
        .scalar()
    )
    github_users = db.query(func.count()).select_from(GitHubUser).scalar()
    confluence_users = (
        db.query(func.count())
        .select_from(ConfluenceUser)
        .filter(ConfluenceUser.account_type == "atlassian")
        .scalar()
    )

    premap_rows = (
        db.query(PreMappingBuffer.source_type, func.count())
        .group_by(PreMappingBuffer.source_type)
        .all()
    )
    premap_map = {source_type: count for source_type, count in premap_rows}

    return SyncStatusCounts(
        jira=SourceUserCount(
            users=jira_users or 0, premap=premap_map.get(SourceType.JIRA, 0)
        ),
        slack=SourceUserCount(
            users=slack_users or 0, premap=premap_map.get(SourceType.SLACK, 0)
        ),
        github=SourceUserCount(
            users=github_users or 0, premap=premap_map.get(SourceType.GITHUB, 0)
        ),
        confluence=SourceUserCount(
            users=confluence_users or 0,
            premap=premap_map.get(SourceType.CONFLUENCE, 0),
        ),
    )


class PremappingStatus(StrEnum):
    ALL = "all"  # 모든 인원
    FULL = "full"  # 모든 협업 툴에 대해 premapping이 생성된 경우
    PARTIAL = "partial"  # 적어도 하나의 premapping이 이루어지지 않은 협업 툴이 존재하는 경우


def _get_user_sync_mappings(
    db: Session, 
    filter_type: PremappingStatus = PremappingStatus.ALL, 
    skip: int = 0, 
    limit: int = 50
) -> tuple[list[UserSyncMapping], int]:
    """협업 도구 매핑 현황 조회 (이메일 직접 조인 및 서브쿼리 최적화)"""

    JMap = aliased(PreMappingBuffer)
    SMap = aliased(PreMappingBuffer)
    GMap = aliased(PreMappingBuffer)

    SModel, _, s_email, s_xf, s_xf_val = SOURCE_MAP[SourceType.SLACK]
    JModel, _, j_email, j_xf, j_xf_val = SOURCE_MAP[SourceType.JIRA]
    GModel, _, g_email, _, _ = SOURCE_MAP[SourceType.GITHUB]

    base_users = (
        select(
            PreMappingBuffer.sub.label("sub"),
            PreMappingBuffer.email.label("email"),
            PreMappingBuffer.name.label("name")
        )
        .distinct(PreMappingBuffer.email)
        .subquery()
    )

    base_stmt = (
        select(
            base_users.c.sub.label("sub"),
            base_users.c.name.label("keycloak_name"),
            base_users.c.email.label("keycloak_email"),
            JModel, 
            SModel, 
            GModel,
            JMap.id.label("j_map_id"),
            SMap.id.label("s_map_id"),
            GMap.id.label("g_map_id")
        )
        .select_from(base_users)
        .outerjoin(JModel, and_(func.lower(base_users.c.email) == func.lower(j_email), j_xf == j_xf_val))
        .outerjoin(SModel, and_(func.lower(base_users.c.email) == func.lower(s_email), s_xf == s_xf_val))
        .outerjoin(GModel, func.lower(base_users.c.email) == func.lower(g_email))
        .outerjoin(JMap, and_(base_users.c.email == JMap.email, JMap.source_type == SourceType.JIRA))
        .outerjoin(SMap, and_(base_users.c.email == SMap.email, SMap.source_type == SourceType.SLACK))
        .outerjoin(GMap, and_(base_users.c.email == GMap.email, GMap.source_type == SourceType.GITHUB))
    )

    # 필터링 적용
    if filter_type == PremappingStatus.FULL:
        base_stmt = base_stmt.where(and_(JMap.id.is_not(None), SMap.id.is_not(None), GMap.id.is_not(None)))
    elif filter_type == PremappingStatus.PARTIAL:
        base_stmt = base_stmt.where(or_(JMap.id.is_(None), SMap.id.is_(None), GMap.id.is_(None)))

    # 전체 개수 조회
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count = db.scalar(count_stmt) or 0

    # 데이터 조회
    data_stmt = (
        base_stmt
        .order_by(base_users.c.email)
        .offset(skip)
        .limit(limit)
    )
    
    rows = db.execute(data_stmt).all()    
    
    results = []
    for row in rows:
        jira_user = row.JiraUser
        slack_user = row.SlackUser
        github_user = row.GitHubUser

        # Jira 정보 조립
        atlassian_info = PreMappingInfo(
            name=getattr(jira_user, "display_name", None),
            identifier=getattr(jira_user, "email_address", None),
            picture=getattr(jira_user, "avatar_url", None)
        ) if jira_user else None

        # Slack 정보 조립
        slack_info = PreMappingInfo(
            name=getattr(slack_user, "real_name", None),
            identifier=getattr(slack_user, "email", None),
            picture=getattr(slack_user, "avatar_url", None)
        ) if slack_user else None

        # GitHub 정보 조립
        github_info = PreMappingInfo(
            name=getattr(github_user, "name", None) or getattr(github_user, "login", None),
            identifier=getattr(github_user, "email", None),
            picture=getattr(github_user, "avatar_url", None)
        ) if github_user else None

        results.append(UserSyncMapping(
            sub=row.sub,
            name=row.keycloak_name, 
            email=row.keycloak_email,
            atlassian=atlassian_info,
            slack=slack_info,
            github=github_info
        ))

    return results, total_count


@router.get(
    path="/users/sync-status",
    description="협업 도구 사용자/프리매핑 현황 및 사용자별 매핑 데이터 (admin 전용)",
)
def get_user_sync_status(
    db: Session = Depends(get_db),
    filter_type: str = Query(description="all, full, partial"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    _admin_user: User = Depends(require_admin_user)
):
    counts = _get_user_sync_counts(db)
    
    skip = calculate_skip(page, size)
    mappings, total_count = _get_user_sync_mappings(
        db=db, 
        filter_type=filter_type, 
        skip=skip, 
        limit=size
    )
        
    return {
        "total": total_count,
        "page": page,
        "size": size,
        "items": mappings,
        "counts": counts
    }


@router.post(
    path="/users/deactivate/{user_id}",
    description="관리자용 사용자 비활성화",
    response_model=DeactivateUserResponse,
)
def deactivate_user(
    user_id: int,
    payload: DeactivateUserRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
):
    return _deactivate_user(
        db=db,
        admin_user=admin_user,
        user_id=user_id,
        reason=payload.reason,
    )


@router.post(
    path="/users/delete/{user_id}",
    description="관리자용 사용자 삭제",
    response_model=DeleteUserResponse,
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
):
    return _delete_user(db=db, admin_user=admin_user, user_id=user_id)


@router.post(
    path="/users/promote/{user_id}",
    description="관리자용 사용자 Admin 승격",
    response_model=PromoteUserResponse,
)
def promote_user_to_admin(
    user_id: int,
    _admin_user: User = Depends(require_admin_user),
):
    with SessionLocal() as db:
        user = promote_user_to_admin_service(
            db,
            user_id=user_id,
        )

        return PromoteUserResponse(
            user_id=user.id,
            role=user.role,
        )


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
    path="/confluence/cloud-ids",
    description="ConfluenceSpace 테이블의 cloud_id 목록(중복 제거) 임시 제공",
    response_model=ConfluenceCloudIdListResponse,
)
def list_confluence_cloud_ids(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    # cloud_id 중복 제거 후 문자열 리스트로 반환
    cloud_ids = [row[0] for row in db.query(ConfluenceSpace.cloud_id).distinct().all()]

    logger.info(
        "[ADMIN][CONFLUENCE][CLOUD_IDS] fetched cloud ids (count=%d)",
        len(cloud_ids),
    )

    return ConfluenceCloudIdListResponse(cloudIds=cloud_ids)


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


@router.get(
    path="/queries",
    response_model=BasePagination[UserQueryWithSaveStatusResponse]
)
def get_admin_query_history(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    target_user_id: Optional[int] = Query(None),
    is_saved: Optional[bool] = Query(None, description="저장 여부 (true/false)"),
    period: str = Query("all", description="today, 7d, 30d, all"),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user)
):
    skip = calculate_skip(page, size)
    
    items, total = get_all_queries_for_admin(
        db=db,
        user_id=target_user_id,
        search_term=search,
        period=period,
        is_saved=is_saved,
        sort=sort,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items
    }


@router.get(
    path="/users",
    response_model=BasePagination[UserResponse],
    description="[어드민] 전체 유저 목록 조회"
)
def get_admin_user_list(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user)
):
    skip = calculate_skip(page, size)
    
    items, total = get_all_users_for_admin(
        db=db,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }


@router.get(
    path="/oauth-users",
    response_model=BasePagination[OAuthUserResponse],
    description="[어드민] 전체 OAuth 유저 목록 조회"
)
def get_admin_user_list(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user)
):
    skip = calculate_skip(page, size)
    
    items, total = get_all_oauth_users_for_admin(
        db=db,
        skip=skip,
        limit=size
    )
    
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }


@router.get(
    path="/{vendor_type}/users",
    response_model=BasePagination[ToolUserResponse],
    description="""
    어드민용: premapping 결과 확인 테이블에서 사용자 정보 수정 시
    선택지로 제공할 협업 툴별 사용자 목록
    """
)
def get_tool_users_by_vendor_type(
    vendor_type: str = Path(..., description="협업 툴 vendor 종류 (github, slack, atlassian)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _check_admin = Depends(require_admin_user)
):
    skip = calculate_skip(page, size)
        
    vendor_map = {
        "github": SourceType.GITHUB,
        "slack": SourceType.SLACK,
        "atlassian": SourceType.JIRA
    }
    
    source_type = vendor_map.get(vendor_type.lower())
    if not source_type:
        raise HTTPException(status_code=400, detail=f"Invalid vendor type: {vendor_type}")
    
    SModel, s_id, s_email, s_xf, s_xf_val = SOURCE_MAP[source_type]
    
    stmt = select(SModel)
    if s_xf is not None:
        stmt = stmt.where(s_xf == s_xf_val)
    
    # 전체 개수 쿼리 최적화
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.scalar(total_stmt) or 0
    
    # 데이터 조회
    rows = db.execute(
        stmt.offset(skip).limit(size)
    ).scalars().all()
    
    items = []
    for user in rows:
        name = (getattr(user, "display_name", None) or 
                getattr(user, "real_name", None) or 
                getattr(user, "name", None) or 
                getattr(user, "login", "Unknown"))
        
        if source_type == SourceType.GITHUB:
            identifier = getattr(user, "login")
        else:
            identifier = getattr(user, "email_address", None) or getattr(user, "email", None)

        picture = getattr(user, "avatar_url", None)

        items.append(ToolUserResponse(
            id=str(getattr(user, s_id.key)),
            name=name,
            identifier=identifier,
            picture=picture,
        ))

    return {
        "total": total_count,
        "page": page,
        "size": size,
        "items": items
    }


@router.patch(
    path="/{vendor_type}/pre-mappings/bulk",
    description="어드민용: Pre-mapping 결과 일괄 수정 적용"
)
def bulk_update_pre_mappings(
    vendor_type: str = Path(...),
    request: PreMappingBulkUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    _check_admin = Depends(require_admin_user)
):
    vendor_map = {
        "github": SourceType.GITHUB,
        "slack": SourceType.SLACK,
        "atlassian": SourceType.JIRA
    }
    source_type = vendor_map.get(vendor_type.lower())
    if not source_type:
        raise HTTPException(status_code=400, detail="Invalid vendor type")
    
    for item in request.items:
        if item.is_ignored:
            # [삭제] 협업 툴 미사용 -> 테이블에서 날림
            db.execute(
                delete(PreMappingBuffer)
                .where(
                    PreMappingBuffer.sub == item.sub,
                    PreMappingBuffer.source_type == source_type
                )
            )
        else:
            # external_user_identifier가 없는 비정상 요청 방어
            if not item.external_user_identifier:
                continue

            # [추가 or 수정]
            buffer = db.query(PreMappingBuffer).filter(
                PreMappingBuffer.sub == item.sub,
                PreMappingBuffer.source_type == source_type
            ).first()

            if buffer:
                # 이미 데이터가 있으면 식별자만 업데이트
                buffer.external_user_identifier = item.external_user_identifier
            else:
                # 데이터가 없으면 새로 생성 (새로운 매핑 추가)
                new_buffer = PreMappingBuffer(
                    sub=item.sub,
                    email=item.email,
                    name=item.name,
                    source_type=source_type,
                    external_user_identifier=item.external_user_identifier
                )
                db.add(new_buffer)

    db.commit()
    return {"message": "success", "processed_count": len(request.items)}
