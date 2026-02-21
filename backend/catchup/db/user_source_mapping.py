from typing import Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.db.models import ConfluenceUser, GitHubUser, JiraUser, OktaUser, PreMappingBuffer, SlackUser, SourceType
from catchup.mapping.schemas import OktaUser as OktaUserSchema


def find_external_user_id_by_email(
    db: Session,
    source_type: SourceType,
    email: str  # 사내 이메일
) -> Optional[str]:
    """사내 이메일을 기준으로 각 협업 도구의 사용자 식별자를 반환한다."""
    
    #(target, filter, extra_filter, extra_filter_value)
    source_map = {
        SourceType.SLACK: (SlackUser.user_id, SlackUser.email, SlackUser.is_bot, False),
        SourceType.JIRA: (JiraUser.account_id, JiraUser.email_address, JiraUser.account_type, 'atlassian'),
        SourceType.CONFLUENCE: (ConfluenceUser.account_id, ConfluenceUser.email, ConfluenceUser.account_type, 'atlassian'),
        SourceType.GITHUB: (GitHubUser.login, GitHubUser.email, None, None),
    }

    target = source_map.get(source_type)
    
    if not target:
        return None

    target_col, filter_col, extra_col, extra_val = target
    
    stmt = (
        select(target_col)
        .where(filter_col == email)
    )
    
    if extra_col is not None:
        stmt = stmt.where(extra_col == extra_val)

    return db.scalar(stmt)


def find_premapped_user_by_email(
    db: Session,
    email: str,
    source_type: SourceType,
) -> Optional[PreMappingBuffer]:
    """사내 이메일과 협업 도구 종류를 기준으로 이미 매핑된 사용자를 조회한다."""
    return db.scalar(
        select(PreMappingBuffer)
        .where(
            PreMappingBuffer.email == email,
            PreMappingBuffer.source_type == source_type
        )
    )


def add_new_mapping(
    db: Session,
    new_mapping: PreMappingBuffer
) -> PreMappingBuffer:
    """새로운 pre-mapping 정보를 추가한다."""
    db.add(new_mapping)
    return new_mapping


def upsert_okta_users(
    db: Session,
    users: list[OktaUserSchema]
):
    """PostgreSQL의 ON CONFLICT를 이용한 Upsert 로직"""
    values = [user.model_dump() for user in users]
    
    stmt = insert(OktaUser).values(values)
    
    # okta_uid가 충돌할 경우(이미 존재할 경우) 업데이트
    update_stmt = stmt.on_conflict_do_update(
        index_elements=['okta_uid'],
        set_={
            "name": stmt.excluded.name,
            "email": stmt.excluded.email,
            "status": stmt.excluded.status,
        }
    )
    
    db.execute(update_stmt)


def get_pending_source_premappings(
    db: Session,
    email: str
) -> Optional[list[PreMappingBuffer]]:
    """
    어드민이 미리 연동해둔 외부 툴 데이터를 찾는다.
    """
    stmt = (
        select(PreMappingBuffer)
        .where(
            (PreMappingBuffer.email == email) &
            (PreMappingBuffer.is_registered == False)
        )
    )
    return db.scalars(stmt).all()