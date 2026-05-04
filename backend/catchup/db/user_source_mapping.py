from typing import Optional

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.db.models import ChannelTalkManager
from catchup.db.models import ConfluenceUser
from catchup.db.models import GitHubUser
from catchup.db.models import JiraUser
from catchup.db.models import OAuthUser
from catchup.db.models import PreMappingBuffer
from catchup.db.models import SlackUser
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.db.models import UserSourceMapping
from catchup.mapping.schemas import OAuthUserSchema

#(user_model, target, filter, extra_filter, extra_filter_value)
SOURCE_MAP = {
    SourceType.SLACK: (SlackUser, SlackUser.user_id, SlackUser.email, SlackUser.is_bot, False),
    SourceType.JIRA: (JiraUser, JiraUser.account_id, JiraUser.email_address, JiraUser.account_type, 'atlassian'),
    SourceType.CONFLUENCE: (ConfluenceUser, ConfluenceUser.account_id, ConfluenceUser.email, ConfluenceUser.account_type, 'atlassian'),
    SourceType.GITHUB: (GitHubUser, GitHubUser.login, GitHubUser.email, None, None),
    SourceType.CHANNEL_TALK: (
        ChannelTalkManager,
        ChannelTalkManager.manager_id,
        ChannelTalkManager.email,
        ChannelTalkManager.removed,
        False,
    ),
}


def _source_extra_condition(extra_col, extra_val):
    if extra_col is None:
        return None
    if extra_val is False:
        return extra_col.is_not(True)
    return extra_col == extra_val

def find_external_user_id_by_email(
    db: Session,
    source_type: SourceType,
    email: str  # 사내 이메일
) -> Optional[str]:
    """사내 이메일을 기준으로 각 협업 도구의 사용자 식별자를 반환한다."""

    target = SOURCE_MAP.get(source_type)
    
    if not target:
        return None

    _, target_col, filter_col, extra_col, extra_val = target
    
    stmt = (
        select(target_col)
        .where(filter_col == email)
    )
    
    if (extra_condition := _source_extra_condition(extra_col, extra_val)) is not None:
        stmt = stmt.where(extra_condition)

    return db.scalar(stmt)


def update_tool_user_email(
    db: Session,
    source_type: SourceType,
    external_user_id: str,
    external_email: str
) -> bool:
    target = SOURCE_MAP.get(source_type)
    if not target:
        return False
    
    model, id_col, email_col, extra_col, extra_val = target
    
    stmt = (
        update(model)
        .where(id_col == external_user_id)
    )
    if (extra_condition := _source_extra_condition(extra_col, extra_val)) is not None:
        stmt = stmt.where(extra_condition)
    stmt = stmt.values({email_col.key: external_email})
    
    result = db.execute(stmt)
    
    return result.rowcount > 0


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


def find_premapped_name_by_external_user_identifier(
    db: Session,
    source_type: SourceType,
    external_user_identifier: str,
) -> Optional[str]:
    """협업 도구 식별자로 매핑된 실명을 조회한다."""
    if not external_user_identifier:
        return None

    return db.scalar(
        select(PreMappingBuffer.name).where(
            PreMappingBuffer.source_type == source_type,
            PreMappingBuffer.external_user_identifier == external_user_identifier,
        )
    )


def find_premapped_names_by_source_type(
    db: Session,
    source_type: SourceType
) -> dict[str, str]:
    """소스 타입별로 external_user_identifier -> 실명 매핑을 조회한다."""
    rows = db.execute(
        select(
            PreMappingBuffer.external_user_identifier,
            PreMappingBuffer.name,
        ).where(PreMappingBuffer.source_type == source_type)
    ).all()

    return {external_user_identifier: name for external_user_identifier, name in rows}


def find_user_id_by_source_mapping(
    db: Session,
    *,
    source_type: SourceType,
    external_user_identifier: str,
) -> int | None:
    if not external_user_identifier:
        return None

    stmt = (
        select(UserSourceMapping.user_id)
        .where(
            UserSourceMapping.source_type == source_type,
            UserSourceMapping.external_user_identifier == external_user_identifier,
        )
    )
    return db.scalar(stmt)


def find_user_names_by_source_mappings(
    db: Session,
    *,
    source_type: SourceType,
    external_user_identifiers: list[str],
) -> dict[str, str]:
    identifiers = list(dict.fromkeys(identifier for identifier in external_user_identifiers if identifier))
    if not identifiers:
        return {}

    rows = db.execute(
        select(
            UserSourceMapping.external_user_identifier,
            User.name,
        )
        .join(User, User.id == UserSourceMapping.user_id)
        .where(
            UserSourceMapping.source_type == source_type,
            UserSourceMapping.external_user_identifier.in_(identifiers),
        )
    ).all()

    return {
        external_user_identifier: name
        for external_user_identifier, name in rows
        if external_user_identifier and name
    }


def add_new_mapping(
    db: Session,
    new_mapping: PreMappingBuffer
) -> PreMappingBuffer:
    """새로운 pre-mapping 정보를 추가한다."""
    db.add(new_mapping)
    return new_mapping


def upsert_user_source_mapping(
    db: Session,
    user_id: int,
    source_type: SourceType,
    external_user_identifier: str,
) -> None:
    """
    UserSourceMapping을 upsert한다.
    (user_id, source_type) 중복 시 external_user_identifier만 갱신.
    """
    stmt = (
        insert(UserSourceMapping)
        .values(
            user_id=user_id,
            source_type=source_type,
            external_user_identifier=external_user_identifier,
        )
        .on_conflict_do_update(
            constraint="uq_user_source",
            set_={"external_user_identifier": external_user_identifier},
        )
    )
    db.execute(stmt)


def upsert_oauth_users(
    db: Session,
    users: list[OAuthUserSchema]
):
    """PostgreSQL의 ON CONFLICT를 이용한 Upsert 로직"""
    
    if not users:
        return

    values = [user.model_dump() for user in users]
    
    stmt = insert(OAuthUser).values(values)
    
    # sub가 충돌할 경우(이미 존재할 경우) 업데이트
    update_stmt = stmt.on_conflict_do_update(
        index_elements=['sub'],
        set_={
            "name": stmt.excluded.name,
            "email": stmt.excluded.email,
            "status": stmt.excluded.status,
        }
    )
    
    db.execute(update_stmt)
    

def delete_deactivated_oauth_users(
    db: Session
) -> int:
    result = db.execute(
        delete(OAuthUser)
        .where(OAuthUser.status == "DEACTIVATED")  # TODO: Keycloak 한정
    )
    
    return result.rowcount


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


def reconcile_missing_user_source_mappings(db: Session) -> int:
    """
    is_registered=True인 PreMappingBuffer 중 UserSourceMapping이 없는 항목을 일괄 생성한다.
    서버 시작 시 한 번 실행하는 멱등성 보장 조치.
    """
    stmt = (
        select(PreMappingBuffer, OAuthUser.user_id)
        .join(OAuthUser, OAuthUser.sub == PreMappingBuffer.sub)
        .outerjoin(
            UserSourceMapping,
            (UserSourceMapping.user_id == OAuthUser.user_id)
            & (UserSourceMapping.source_type == PreMappingBuffer.source_type),
        )
        .where(
            PreMappingBuffer.is_registered == True,
            OAuthUser.user_id.isnot(None),
            UserSourceMapping.user_id.is_(None),
        )
    )
    rows = db.execute(stmt).all()

    for buffer, user_id in rows:
        db.add(
            UserSourceMapping(
                user_id=user_id,
                source_type=buffer.source_type,
                external_user_identifier=buffer.external_user_identifier,
            )
        )
    return len(rows)
