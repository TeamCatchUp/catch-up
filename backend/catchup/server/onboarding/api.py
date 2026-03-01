from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user, get_pending_signup_user
from catchup.connectors.atlassian import oauth_client
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.models import ConfluenceUser, GitHubUser, JiraUser, KnowledgeSource, PreMappingBuffer, SlackUser, SourceType, User
from catchup.onboarding.oauth import OAuthClient, sync_initial_oauth_users
from catchup.onboarding.admin import register_admin_from_oauth
from catchup.onboarding.schemas import AdminSignUpRequest, AdminSignUpSchema, CandidateItem, MappingCandidates, UserSignUpRequest, SignUpResponse, UserSignUpSchema
from catchup.onboarding.user import register_user_from_oauth
from catchup.server.state import state


router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["onboarding"]
)

@router.post(
    path="",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="OAuth 유저 최초 회원가입 및 정보 매핑",
)
def signup_oauth_user(
    payload: UserSignUpRequest,
    pending_user: dict = Depends(get_pending_signup_user),
    db: Session = Depends(get_db)
):
    if not state.is_admin_initiated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="시스템 초기 설정이 필요합니다. 관리자가 먼저 등록되어야 합니다."
        )

    signup_data = UserSignUpSchema(
        sub=pending_user["sub"],
        email=pending_user["email"],
        name=payload.name,
        department=payload.department,
        job_level=payload.job_level,
    )
    
    new_user = register_user_from_oauth(db, signup_data)

    return new_user


@router.post(
    path="/admin",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="루트 어드민 온보딩",
    description="루트 어드민이 회사를 등록하고 워크스페이스를 생성한다."
)
async def signup_oauth_admin(
    payload: AdminSignUpRequest,
    background_tasks: BackgroundTasks,
    pending_user: dict = Depends(get_pending_signup_user),
    db: Session = Depends(get_db)
):
    if state.is_admin_initiated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이미 관리자가 등록되어 있으므로 일반 유저로 가입해야 합니다."
        )
    
    admin_data = AdminSignUpSchema(
        sub=pending_user["sub"],
        email=pending_user["email"],
        name=payload.name,
        job_level=payload.job_level,
        company_name=payload.company_name,
        company_size=payload.company_size,
        workspace_name=payload.workspace_name
    )
    
    # Admin 등록
    new_admin = await run_in_threadpool(
        register_admin_from_oauth,
        db,
        admin_data
    )
    
    # OAuth 사용자 목록 저장
    background_tasks.add_task(sync_initial_oauth_users)

    state.is_admin_initiated = True
    
    return new_admin


TOOL_META_MAP = {
    SourceType.SLACK: (SlackUser, SlackUser.user_id, "display_name", "avatar_url"),
    SourceType.GITHUB: (GitHubUser, GitHubUser.login, "name", "avatar_url"),
    SourceType.JIRA: (JiraUser, JiraUser.account_id, "display_name", "avatar_url"),
    SourceType.CONFLUENCE: (ConfluenceUser, ConfluenceUser.account_id, "display_name", "avatar_url")
}

# TODO: 책임 분리
@router.get(
    path="/mapping/results",
    response_model=Optional[list[MappingCandidates]],
    description="""
    로그인한 사용자의 이메일을 기준으로 외부 계정 매핑 후보를 수집하고,
    외부 사용자 상세 정보를 병합한 뒤, 벤더 단위로 그룹화한 결과를 반환한다.
    """
)
def get_mapping_candidate_by_tools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 외부 연동 툴
    active_sources: list[SourceType] = db.scalars(
        select(KnowledgeSource.source_type)
        .where(
            (KnowledgeSource.is_active == True) &
            (KnowledgeSource.workspace_id == current_user.workspace_links[0].workspace_id)  # TODO: 워크 스페이스 늘어나는 경우 수정 필요
        )
        .distinct()
    ).all()
    
    # 로그인한 사용자의 이메일에 해당하는 버퍼 조회
    my_candidates: list[PreMappingBuffer] = db.scalars(
        select(PreMappingBuffer)
        .where(
            (PreMappingBuffer.is_registered == False) &
            (PreMappingBuffer.email == current_user.email)
        )
    ).all()
    
    ids_by_source = {source: [] for source in active_sources}
    for c in my_candidates:
        if c.source_type in ids_by_source:
            ids_by_source[c.source_type].append(c.external_user_identifier)
            
    global_user_map = {}
    for source, ids in ids_by_source.items():
        if not ids or source not in TOOL_META_MAP:
            continue
        
        model, id_col, name_attr, pic_attr = TOOL_META_MAP[source]
        
        records = db.scalars(
            select(model)
            .where(id_col.in_(ids))
        ).all()
        
        for record in records:
            external_id = getattr(record, id_col.name)
            global_user_map[(source, external_id)] = {
                "display_name": getattr(record, name_attr, None),
                "picture": getattr(record, pic_attr, None)
            }
    
    grouped_data = {}
    for source in active_sources:
        display_name = _get_display_source_name(source)
        if display_name not in grouped_data:
            grouped_data[display_name] = []
            
    for candidate in my_candidates:
        original_source = candidate.source_type
        display_group = _get_display_source_name(original_source)
        
        if display_group not in grouped_data:
            continue
        
        external_id = candidate.external_user_identifier
        full_name = candidate.name or ""
        email = candidate.email or ""
        display_name = full_name if full_name else email
        picture = None
        
        detail_info = global_user_map.get((original_source, external_id))
        if detail_info:
            display_name = detail_info["display_name"] or display_name
            picture = detail_info["picture"]
        
        item = CandidateItem(
            external_id=external_id,
            full_name=full_name,
            display_name=display_name,
            email=email,
            picture=picture,
        )
        grouped_data[display_group].append(item)
        
    response_data = [
        MappingCandidates(
            source_type=source,
            candidates=items
        )
        for source, items in grouped_data.items()
    ]
    
    return response_data

def _get_display_source_name(source) -> str:
    if isinstance(source, str):
        source_str = source
    else:
        source_str = source.value
        
    if source_str in ("jira", "confluence"):
        return "atlassian"
        
    return source_str