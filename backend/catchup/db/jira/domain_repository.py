"""
Jira 엔티티 CRUD 함수

JiraProject, JiraSprint, JiraUser 테이블에 대한 CRUD 작업 수행.
정적 데이터를 RDBMS에 저장하고 조회.
"""

from datetime import datetime, timezone

from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from catchup.db.models import JiraProject, JiraSprint, JiraUser


def _user_email_update_value(stmt):
    return func.coalesce(stmt.excluded.email_address, JiraUser.email_address)


def _user_upsert_set(stmt) -> dict:
    return {
        "account_type": stmt.excluded.account_type,
        "active": stmt.excluded.active,
        "display_name": stmt.excluded.display_name,
        "email_address": _user_email_update_value(stmt),
        "avatar_url": stmt.excluded.avatar_url,
        "self_url": stmt.excluded.self_url,
        "synced_at": stmt.excluded.synced_at,
    }


# ============================================================
# Project CRUD
# ============================================================

def upsert_project(
    db: Session,
    cloud_id: str,
    project_key: str,
    project_id: str,
    project_name: str,
    description: str | None = None,
    project_type: str | None = None,
    lead_account_id: str | None = None,
    lead_display_name: str | None = None,
    url: str | None = None,
) -> JiraProject:
    """
    프로젝트 Upsert (Insert or Update)
    """
    now = datetime.now(timezone.utc)

    stmt = insert(JiraProject).values(
        cloud_id=cloud_id,
        project_key=project_key,
        project_id=project_id,
        project_name=project_name,
        description=description,
        project_type=project_type,
        lead_account_id=lead_account_id,
        lead_display_name=lead_display_name,
        url=url,
        synced_at=now,
    ).on_conflict_do_update(
        index_elements=["cloud_id", "project_key"],
        set_={
            "project_id": project_id,
            "project_name": project_name,
            "description": description,
            "project_type": project_type,
            "lead_account_id": lead_account_id,
            "lead_display_name": lead_display_name,
            "url": url,
            "synced_at": now,
        }
    )
    db.execute(stmt)
    db.flush()

    return get_project(db, cloud_id, project_key)


def upsert_projects_bulk(db: Session, projects: list[dict]) -> int:
    """
    프로젝트 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        projects: 프로젝트 데이터 딕셔너리 리스트

    Returns:
        처리된 프로젝트 수
    """
    if not projects:
        return 0

    now = datetime.now(timezone.utc)
    for project in projects:
        project["synced_at"] = now

    stmt = insert(JiraProject).values(projects)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cloud_id", "project_key"],
        set_={
            "project_id": stmt.excluded.project_id,
            "project_name": stmt.excluded.project_name,
            "description": stmt.excluded.description,
            "project_type": stmt.excluded.project_type,
            "lead_account_id": stmt.excluded.lead_account_id,
            "lead_display_name": stmt.excluded.lead_display_name,
            "url": stmt.excluded.url,
            "synced_at": stmt.excluded.synced_at,
        }
    )
    db.execute(stmt)

    return len(projects)

def sync_projects_snapshot(
    db: Session,
    cloud_id: str,
    projects: list[dict],
) -> dict[str, int]:
    now = datetime.now(timezone.utc)

    if not projects:
        delete_stmt = delete(JiraProject).where(JiraProject.cloud_id == cloud_id)
        delete_result = db.execute(delete_stmt)
        return {
            "upserted": 0,
            "deleted": delete_result.rowcount or 0,
        }
    
    normalized_projects: list[dict] = []
    fetched_project_keys: list[str] = []

    for project in projects:
        project_key = project.get("project_key")
        if not project_key:
            continue

        normalized_projects.append(
            {
                "cloud_id": cloud_id,
                "project_key": project_key,
                "project_id": project.get("project_id", ""),
                "project_name": project.get("project_name", ""),
                "description": project.get("description"),
                "project_type": project.get("project_type"),
                "lead_account_id": project.get("lead_account_id"),
                "lead_display_name": project.get("lead_display_name"),
                "url": project.get("url"),
                "synced_at": now, 
            }
        )
        fetched_project_keys.append(project_key)

    if not normalized_projects:
        delete_stmt = delete(JiraProject).where(JiraProject.cloud_id==cloud_id)
        delete_result = db.execute(delete_stmt)
        return {
            "upserted": 0,
            "deleted": delete_result.rowcount or 0,
        }
    
    upsert_stmt = insert(JiraProject).values(normalized_projects)
    upsert_stmt = upsert_stmt.on_conflict_do_update(
        index_elements=["cloud_id", "project_key"],
        set_={
            "project_id": upsert_stmt.excluded.project_id,
            "project_name": upsert_stmt.excluded.project_name,
            "description": upsert_stmt.excluded.description,
            "project_type": upsert_stmt.excluded.project_type,
            "lead_account_id": upsert_stmt.excluded.lead_account_id,
            "lead_display_name": upsert_stmt.excluded.lead_display_name,
            "url": upsert_stmt.excluded.url,
            "synced_at": upsert_stmt.excluded.synced_at,
        },
    )
    db.execute(upsert_stmt)

    stale_delete_stmt = delete(JiraProject).where(
        JiraProject.cloud_id == cloud_id,
        ~JiraProject.project_key.in_(fetched_project_keys),
    )
    stale_delete_result = db.execute(stale_delete_stmt)

    return {
        "upserted": len(normalized_projects),
        "deleted": stale_delete_result.rowcount or 0,
    }



def get_project(db: Session, cloud_id: str, project_key: str) -> JiraProject | None:
    """프로젝트 조회"""
    stmt = select(JiraProject).where(
        JiraProject.cloud_id == cloud_id,
        JiraProject.project_key == project_key,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_projects_by_cloud_id(db: Session, cloud_id: str) -> list[JiraProject]:
    """Cloud의 모든 프로젝트 조회"""
    stmt = (
        select(JiraProject)
        .where(JiraProject.cloud_id == cloud_id)
        .order_by(JiraProject.project_key)
    )
    return list(db.execute(stmt).scalars().all())


def get_projects_by_keys(
    db: Session,
    cloud_id: str,
    project_keys: list[str],
) -> dict[str, JiraProject]:
    """
    특정 project_key 목록으로 프로젝트 조회

    Returns:
        project_key → JiraProject 매핑 딕셔너리
    """
    if not project_keys:
        return {}

    stmt = select(JiraProject).where(
        JiraProject.cloud_id == cloud_id,
        JiraProject.project_key.in_(project_keys),
    )
    projects = db.execute(stmt).scalars().all()
    return {p.project_key: p for p in projects}


def delete_project(db: Session, cloud_id: str, project_key: str) -> int:
    """프로젝트 삭제"""
    stmt = delete(JiraProject).where(
        JiraProject.cloud_id == cloud_id,
        JiraProject.project_key == project_key,
    )
    result = db.execute(stmt)
    return result.rowcount


def delete_projects_by_cloud_id(db: Session, cloud_id: str) -> int:
    """Cloud의 모든 프로젝트 삭제"""
    stmt = delete(JiraProject).where(JiraProject.cloud_id == cloud_id)
    result = db.execute(stmt)
    return result.rowcount


# ============================================================
# Sprint CRUD
# ============================================================

def upsert_sprint(
    db: Session,
    cloud_id: str,
    sprint_id: int,
    sprint_name: str,
    state: str | None = None,
    goal: str | None = None,
    project_key: str | None = None,
    board_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    complete_date: datetime | None = None,
) -> JiraSprint:
    """
    스프린트 Upsert (Insert or Update)
    """
    now = datetime.now(timezone.utc)

    stmt = insert(JiraSprint).values(
        cloud_id=cloud_id,
        sprint_id=sprint_id,
        sprint_name=sprint_name,
        state=state,
        goal=goal,
        project_key=project_key,
        board_id=board_id,
        start_date=start_date,
        end_date=end_date,
        complete_date=complete_date,
        synced_at=now,
    ).on_conflict_do_update(
        index_elements=["cloud_id", "sprint_id"],
        set_={
            "sprint_name": sprint_name,
            "state": state,
            "goal": goal,
            "project_key": project_key,
            "board_id": board_id,
            "start_date": start_date,
            "end_date": end_date,
            "complete_date": complete_date,
            "synced_at": now,
        }
    )
    db.execute(stmt)
    db.flush()

    return get_sprint(db, cloud_id, sprint_id)


def upsert_sprints_bulk(
    db: Session,
    sprints: list[dict],
) -> int:
    """
    스프린트 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        sprints: 스프린트 데이터 딕셔너리 리스트

    Returns:
        처리된 스프린트 수
    """
    if not sprints:
        return 0

    now = datetime.now(timezone.utc)
    for sprint in sprints:
        sprint["synced_at"] = now

    stmt = insert(JiraSprint).values(sprints)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cloud_id", "sprint_id"],
        set_={
            "sprint_name": stmt.excluded.sprint_name,
            "state": stmt.excluded.state,
            "goal": stmt.excluded.goal,
            "project_key": stmt.excluded.project_key,
            "board_id": stmt.excluded.board_id,
            "start_date": stmt.excluded.start_date,
            "end_date": stmt.excluded.end_date,
            "complete_date": stmt.excluded.complete_date,
            "synced_at": stmt.excluded.synced_at,
        }
    )
    db.execute(stmt)
    return len(sprints)


def get_sprint(db: Session, cloud_id: str, sprint_id: int) -> JiraSprint | None:
    """스프린트 조회"""
    stmt = select(JiraSprint).where(
        JiraSprint.cloud_id == cloud_id,
        JiraSprint.sprint_id == sprint_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_sprints_by_cloud_id(
    db: Session,
    cloud_id: str,
    state: str | None = None,
) -> list[JiraSprint]:
    """Cloud의 모든 스프린트 조회"""
    stmt = select(JiraSprint).where(JiraSprint.cloud_id == cloud_id)
    if state:
        stmt = stmt.where(JiraSprint.state == state)
    stmt = stmt.order_by(JiraSprint.start_date.desc().nulls_last())
    return list(db.execute(stmt).scalars().all())


def get_sprints_by_ids(
    db: Session,
    cloud_id: str,
    sprint_ids: list[int],
) -> dict[int, JiraSprint]:
    """
    특정 sprint_id 목록으로 스프린트 조회

    Returns:
        sprint_id → JiraSprint 매핑 딕셔너리
    """
    if not sprint_ids:
        return {}

    stmt = select(JiraSprint).where(
        JiraSprint.cloud_id == cloud_id,
        JiraSprint.sprint_id.in_(sprint_ids),
    )
    sprints = db.execute(stmt).scalars().all()
    return {s.sprint_id: s for s in sprints}


def get_sprint_by_name(
    db: Session,
    cloud_id: str,
    sprint_name: str,
) -> JiraSprint | None:
    """스프린트 이름으로 조회 (Issue 변환 시 사용)"""
    stmt = select(JiraSprint).where(
        JiraSprint.cloud_id == cloud_id,
        JiraSprint.sprint_name == sprint_name,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_sprints_by_project_key(
    db: Session,
    cloud_id: str,
    project_key: str,
) -> list[JiraSprint]:
    """프로젝트의 모든 스프린트 조회"""
    stmt = (
        select(JiraSprint)
        .where(
            JiraSprint.cloud_id == cloud_id,
            JiraSprint.project_key == project_key,
        )
        .order_by(JiraSprint.start_date.desc().nulls_last())
    )
    return list(db.execute(stmt).scalars().all())


def delete_sprint(db: Session, cloud_id: str, sprint_id: int) -> int:
    """스프린트 삭제"""
    stmt = delete(JiraSprint).where(
        JiraSprint.cloud_id == cloud_id,
        JiraSprint.sprint_id == sprint_id,
    )
    result = db.execute(stmt)
    return result.rowcount


def delete_sprints_by_cloud_id(db: Session, cloud_id: str) -> int:
    """Cloud의 모든 스프린트 삭제"""
    stmt = delete(JiraSprint).where(JiraSprint.cloud_id == cloud_id)
    result = db.execute(stmt)
    return result.rowcount


# ============================================================
# User CRUD
# ============================================================

def upsert_user(
    db: Session,
    cloud_id: str,
    account_id: str,
    display_name: str,
    account_type: str = "atlassian",
    active: bool = True,
    email_address: str | None = None,
    avatar_url: str | None = None,
    self_url: str | None = None,
) -> JiraUser:
    """
    사용자 Upsert (Insert or Update)
    """
    now = datetime.now(timezone.utc)

    stmt = insert(JiraUser).values(
        cloud_id=cloud_id,
        account_id=account_id,
        account_type=account_type,
        active=active,
        display_name=display_name,
        email_address=email_address,
        avatar_url=avatar_url,
        self_url=self_url,
        synced_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["cloud_id", "account_id"],
        set_=_user_upsert_set(stmt),
    )
    db.execute(stmt)
    db.flush()

    return get_user(db, cloud_id, account_id)


def upsert_users_bulk(
    db: Session,
    users: list[dict],
) -> int:
    """
    사용자 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        users: 사용자 데이터 딕셔너리 리스트
            각 딕셔너리에는 cloud_id, account_id, display_name 필수

    Returns:
        처리된 사용자 수
    """
    if not users:
        return 0

    now = datetime.now(timezone.utc)
    for user in users:
        user["synced_at"] = now
        # 기본값 설정
        user.setdefault("account_type", "atlassian")
        user.setdefault("active", True)

    stmt = insert(JiraUser).values(users)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cloud_id", "account_id"],
        set_=_user_upsert_set(stmt),
    )
    db.execute(stmt)
    return len(users)


def get_user(db: Session, cloud_id: str, account_id: str) -> JiraUser | None:
    """사용자 조회"""
    stmt = select(JiraUser).where(
        JiraUser.cloud_id == cloud_id,
        JiraUser.account_id == account_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_users_by_cloud_id(
    db: Session,
    cloud_id: str,
    include_inactive: bool = False,
) -> list[JiraUser]:
    """Cloud의 모든 사용자 조회"""
    stmt = select(JiraUser).where(JiraUser.cloud_id == cloud_id)
    if not include_inactive:
        stmt = stmt.where(JiraUser.active == True)
    stmt = stmt.order_by(JiraUser.display_name)
    return list(db.execute(stmt).scalars().all())


def get_users_by_account_ids(
    db: Session,
    cloud_id: str,
    account_ids: list[str],
) -> dict[str, JiraUser]:
    """
    특정 account_id 목록으로 사용자 조회

    Returns:
        account_id → JiraUser 매핑 딕셔너리
    """
    if not account_ids:
        return {}

    stmt = select(JiraUser).where(
        JiraUser.cloud_id == cloud_id,
        JiraUser.account_id.in_(account_ids),
    )
    users = db.execute(stmt).scalars().all()
    return {u.account_id: u for u in users}


def delete_user(db: Session, cloud_id: str, account_id: str) -> int:
    """사용자 삭제"""
    stmt = delete(JiraUser).where(
        JiraUser.cloud_id == cloud_id,
        JiraUser.account_id == account_id,
    )
    result = db.execute(stmt)
    return result.rowcount


def delete_users_by_cloud_id(db: Session, cloud_id: str) -> int:
    """Cloud의 모든 사용자 삭제"""
    stmt = delete(JiraUser).where(JiraUser.cloud_id == cloud_id)
    result = db.execute(stmt)
    return result.rowcount
