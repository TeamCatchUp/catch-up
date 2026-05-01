import logging
from enum import StrEnum
from typing import Optional

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from sqlalchemy import and_
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased

from catchup.audit.actions import UserRoleAction
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import AdminOAuthAuditMetadata
from catchup.audit.metadata import UserAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.audit.utils import audit_log
from catchup.auth.dependencies import require_admin_user
from catchup.chat.schemas import UserQueryWithSaveStatusResponse
from catchup.db.chat_room import get_all_queries_for_admin
from catchup.db.dependencies import get_db
from catchup.db.models import ConfluenceSpace
from catchup.db.models import ConfluenceUser
from catchup.db.models import GithubRepository
from catchup.db.models import GitHubUser
from catchup.db.models import JiraAccountType
from catchup.db.models import JiraProject
from catchup.db.models import JiraUser
from catchup.db.models import PreMappingBuffer
from catchup.db.models import SlackUser
from catchup.db.models import SourceType
from catchup.db.models import SyncConnector
from catchup.db.models import User
from catchup.db.sync.admin_connector_status import AdminConnectorTargetRangeRow
from catchup.db.sync.admin_connector_status import (
    list_admin_connector_target_range_rows,
)
from catchup.db.user_source_mapping import SOURCE_MAP
from catchup.db.users import get_all_oauth_users_for_admin
from catchup.db.users import get_all_users_for_admin
from catchup.events.enums import AdminOAuthAction
from catchup.events.enums import EventType
from catchup.onboarding.oauth import sync_initial_keycloak_users
from catchup.server.admin.schemas import AdminChannelTalkConnectorTargetRangeResponse
from catchup.server.admin.schemas import AdminConnectorStatusResponse
from catchup.server.admin.schemas import AdminConnectorTargetRangeResponse
from catchup.server.admin.schemas import AdminUserDetailResponse
from catchup.server.admin.schemas import AdminUserListItem
from catchup.server.admin.schemas import AdminUserListResponse
from catchup.server.admin.schemas import ChannelTalkConnectorTargetType
from catchup.server.admin.schemas import ConfluenceAccount
from catchup.server.admin.schemas import ConfluenceCloudIdListResponse
from catchup.server.admin.schemas import ConnectorResourceType
from catchup.server.admin.schemas import ConnectorStatusSource
from catchup.server.admin.schemas import DeactivateUserRequest
from catchup.server.admin.schemas import DeactivateUserResponse
from catchup.server.admin.schemas import DeleteUserRequest
from catchup.server.admin.schemas import DeleteUserResponse
from catchup.server.admin.schemas import GithubAccount
from catchup.server.admin.schemas import JiraAccount
from catchup.server.admin.schemas import OAuthUserResponse
from catchup.server.admin.schemas import PreMappingBulkUpdateRequest
from catchup.server.admin.schemas import PreMappingInfo
from catchup.server.admin.schemas import PromoteUserRequest
from catchup.server.admin.schemas import PromoteUserResponse
from catchup.server.admin.schemas import RevokeUserRequest
from catchup.server.admin.schemas import RevokeUserResponse
from catchup.server.admin.schemas import SlackAccount
from catchup.server.admin.schemas import SourceUserCount
from catchup.server.admin.schemas import SyncStatusCounts
from catchup.server.admin.schemas import ToolUserResponse
from catchup.server.admin.schemas import UserIntegrations
from catchup.server.admin.schemas import UserResponse
from catchup.server.admin.schemas import UserSyncMapping
from catchup.server.auth.schemas import ConfluenceSyncableResponse
from catchup.server.auth.schemas import ConfluenceSyncableSpace
from catchup.server.auth.schemas import GithubSyncableRepository
from catchup.server.auth.schemas import GithubSyncableResponse
from catchup.server.auth.schemas import JiraSyncableProject
from catchup.server.auth.schemas import JiraSyncableResponse
from catchup.server.schemas import BasePagination
from catchup.server.schemas import calculate_skip
from catchup.user.role_service import promote_admin_role
from catchup.user.role_service import revoke_admin_role
from catchup.user.status_service import deactivate_user as deactivate_user_service
from catchup.user.status_service import delete_user as delete_user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def _format_date(dt):
    if not dt:
        return None
    try:
        return dt.date().isoformat()
    except Exception:
        return None


def _format_datetime(dt):
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def _get_connector_status_spec(source: ConnectorStatusSource):
    if source == ConnectorStatusSource.GITHUB:
        return SyncConnector.GITHUB, ConnectorResourceType.REPOSITORIES
    if source == ConnectorStatusSource.JIRA:
        return SyncConnector.JIRA, ConnectorResourceType.PROJECTS
    if source == ConnectorStatusSource.SLACK:
        return SyncConnector.SLACK, ConnectorResourceType.CHANNELS
    if source == ConnectorStatusSource.CONFLUENCE:
        return SyncConnector.CONFLUENCE, ConnectorResourceType.SPACES
    if source == ConnectorStatusSource.CHANNEL_TALK:
        return SyncConnector.CHANNEL_TALK, ConnectorResourceType.CHANNEL_TALK_TARGETS
    raise HTTPException(status_code=400, detail="unsupported source")


def _build_connector_status_target_response(
    row: AdminConnectorTargetRangeRow,
    *,
    source: ConnectorStatusSource,
) -> AdminConnectorTargetRangeResponse:
    fields = {
        "scope_id": row.scope_id,
        "target_id": row.target_id,
        "target_name": row.target_name,
        "event_id": row.event_id,
        "sync_status": row.sync_status,
        "last_succeeded_at": _format_datetime(row.last_succeeded_at),
        "last_failed_at": _format_datetime(row.last_failed_at),
        "oldest": _format_date(row.oldest_at),
        "latest": _format_date(row.latest_at),
    }
    if source == ConnectorStatusSource.CHANNEL_TALK:
        return AdminChannelTalkConnectorTargetRangeResponse(
            **fields,
            target_type=ChannelTalkConnectorTargetType(row.target_type),
        )
    return AdminConnectorTargetRangeResponse(**fields)


def _get_connector_status(
    db: Session,
    *,
    source: ConnectorStatusSource,
) -> AdminConnectorStatusResponse:
    connector, resource_type = _get_connector_status_spec(source)
    target_rows = list_admin_connector_target_range_rows(
        db,
        connector=connector,
    )
    return AdminConnectorStatusResponse(
        source=source,
        resource_type=resource_type,
        total_targets=len(target_rows),
        targets=[
            _build_connector_status_target_response(
                row,
                source=source,
            )
            for row in target_rows
        ],
    )


@router.get(
    path="/connector/status",
    description="source별 sync target의 pg embedding 데이터 범위 조회 (admin 전용)",
    response_model=AdminConnectorStatusResponse,
)
def get_connector_status(
    source: ConnectorStatusSource = Query(
        ...,
        description="github, jira, slack, confluence, channel_talk",
    ),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    return _get_connector_status(db, source=source)

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
    path="/users/deactivate",
    description="관리자용 사용자 비활성화",
    response_model=DeactivateUserResponse,
)
def deactivate_user(
    payload: DeactivateUserRequest,
    admin_user: User = Depends(require_admin_user),
):
    result = deactivate_user_service(
        admin_user_id=admin_user.id,
        user_id=payload.userId,
        reason=payload.reason,
    )
    return DeactivateUserResponse(
        userId=result.user_id,
        status=result.status,
        deactivatedAt=result.deactivated_at,
        reason=result.reason,
    )


@router.post(
    path="/users/delete",
    description="관리자용 사용자 삭제",
    response_model=DeleteUserResponse,
)
def delete_user(
    payload: DeleteUserRequest,
    admin_user: User = Depends(require_admin_user),
):
    result = delete_user_service(
        admin_user_id=admin_user.id,
        user_id=payload.userId,
        reason=payload.reason,
    )
    return DeleteUserResponse(
        userId=result.user_id,
        status=result.status,
        deletedAt=result.deleted_at,
        reason=result.reason,
    )


@router.post(
    path="/users/promote",
    description="관리자용 사용자 Admin 승격",
    response_model=PromoteUserResponse,
)
@audit_log(
    UserRoleAction.PROMOTE,
    metadata_factory=UserAuditMetadata.from_audit,
    emit_attempt=True,
)
def promote_user_to_admin(
    payload: PromoteUserRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
):
    result = promote_admin_role(
        db,
        user_id=payload.userId,
        actor_user_id=admin_user.id,
        reason=payload.reason,
    )

    return result


@router.post(
    path="/users/revoke",
    description="관리자용 사용자 Admin 권한 회수",
    response_model=RevokeUserResponse,
)
@audit_log(
    UserRoleAction.REVOKE_ADMIN,
    metadata_factory=UserAuditMetadata.from_audit,
    emit_attempt=True,
)
def revoke_admin_role_from_user(
    payload: RevokeUserRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_user),
):
    result = revoke_admin_role(
        db,
        user_id=payload.userId,
        actor_user_id=admin_user.id,
        reason=payload.reason,
    )

    return result

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
def get_admin_oauth_user_list(
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

@router.post(
    path='/oauth-users',
    description="[어드민] OAuth 유저 동기화"
)
async def sync_oauth_user_list(
    _admin: User = Depends(require_admin_user)
):
    emit_audit_event(
        event_type=EventType.OAUTH,
        event_action=AdminOAuthAction.SYNC_USERS,
        event_status=AuditEventStatus.ATTEMPT,
        level=AuditLevel.INFO
    )
    
    try:
        await sync_initial_keycloak_users()

    except Exception as e:
        emit_audit_event(
            event_type=EventType.OAUTH,
            event_action=AdminOAuthAction.SYNC_USERS,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=AdminOAuthAuditMetadata(
                context=str(e)
            )
        )
        raise HTTPException(
            status_code=500, 
            detail="OAuth 유저 동기화 실패"
        )

    emit_audit_event(
        event_type=EventType.OAUTH,
        event_action=AdminOAuthAction.SYNC_USERS,
        event_status=AuditEventStatus.SUCCESS,
        level=AuditLevel.INFO
    )
    
    return {"message": "success"}



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
