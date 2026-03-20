"""
GitHub Entities CRUD 함수

GitHubRepository 테이블에 대한 CRUD 작업 수행.
Installation에 연결된 Repository 정보를 관리.
"""

from gettext import install
import json
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select, delete, and_, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.db.models import (
    GithubRepository as GitHubRepositoryModel,
    GitHubUser as GitHubUserModel,
)

class RepositoryUpsertData(BaseModel):
    """Repository Upsert용 DB 전용 DTO"""
    repo_id: int
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str | None = None
    default_branch: str = "main"
    language: str | None = None
    topics: list[str] | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    private: bool = False
    archived: bool = False
    disabled: bool = False
    pushed_at: datetime | None = None
    repo_created_at: datetime | None = None
    repo_updated_at: datetime | None = None


class UserUpsertData(BaseModel):
    """User Upsert용 DB 전용 DTO"""
    database_id: int
    login: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    org_role: str | None = None

def get_repository(
    db: Session,
    installation_id: int,
    full_name: str,
) -> GitHubRepositoryModel | None:
    """Repository 조회 by full_name"""
    stmt = select(GitHubRepositoryModel).where(
        and_(
            GitHubRepositoryModel.installation_id == installation_id,
            GitHubRepositoryModel.full_name == full_name,
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_repository_by_id(
    db: Session,
    repo_id: int,
) -> GitHubRepositoryModel | None:
    """Repository 조회 by GitHub repo ID"""
    stmt = select(GitHubRepositoryModel).where(
        GitHubRepositoryModel.repo_id == repo_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_repositories_by_ids(
    db: Session,
    installation_id: int,
    repo_ids: list[int],
) -> list[GitHubRepositoryModel]:
    if not repo_ids:
        return []

    stmt = (
        select(GitHubRepositoryModel)
        .where(
            and_(
                GitHubRepositoryModel.installation_id == installation_id,
                GitHubRepositoryModel.repo_id.in_(repo_ids),
            )
        )
    )
    return list(db.execute(stmt).scalars().all())


def get_repositories_by_installation(
    db: Session,
    installation_id: int,
) -> list[GitHubRepositoryModel]:
    """Installation의 모든 Repository 조회"""
    stmt = (
        select(GitHubRepositoryModel)
        .where(GitHubRepositoryModel.installation_id == installation_id)
        .order_by(GitHubRepositoryModel.full_name)
    )
    return list(db.execute(stmt).scalars().all())


def upsert_repositories_bulk(
    db: Session,
    installation_id: int,
    repos_data: list[RepositoryUpsertData],
) -> int:
    """
    Repository 정보 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repos_data: Repository Upsert DTO 리스트

    Returns:
        Upsert된 Repository 수
    """
    if not repos_data:
        return 0

    now = datetime.now(timezone.utc)
    values_list = []

    for repo in repos_data:
        values_list.append({
            "installation_id": installation_id,
            "repo_id": repo.repo_id,
            "owner": repo.owner,
            "name": repo.name,
            "full_name": repo.full_name,
            "html_url": repo.html_url,
            "description": repo.description,
            "default_branch": repo.default_branch,
            "language": repo.language,
            "topics": json.dumps(repo.topics) if repo.topics else None,
            "stargazers_count": repo.stargazers_count,
            "forks_count": repo.forks_count,
            "open_issues_count": repo.open_issues_count,
            "private": repo.private,
            "archived": repo.archived,
            "disabled": repo.disabled,
            "pushed_at": repo.pushed_at,
            "repo_created_at": repo.repo_created_at,
            "repo_updated_at": repo.repo_updated_at,
            "synced_at": now,
        })

    stmt = insert(GitHubRepositoryModel).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["repo_id"],
        set_=_repo_upsert_set(stmt),
    )

    db.execute(stmt)
    db.commit()

    return len(values_list)

def sync_repositories_snapshot(
    db: Session,
    installation_id: int,
    repos_data: list[RepositoryUpsertData],
    *,
    auto_commit: bool = True,
) -> dict[str, int]:
    """
    Installation 단위 Repository 스냅샷 동기화
    """
    now = datetime.now(timezone.utc)

    if not repos_data:
        delete_stmt = delete(GitHubRepositoryModel).where(
            GitHubRepositoryModel.installation_id == installation_id
        )
        delete_result = db.execute(delete_stmt)
        if auto_commit:
            db.commit()
        else:
            db.flush()
        return {
            "upserted": 0,
            "deleted": delete_result.rowcount or 0,
        }
    
    values_list: list[dict] = []
    fetched_repo_ids: list[int] = []

    for repo in repos_data:
        fetched_repo_ids.append(repo.repo_id)
        values_list.append(
            {
                "installation_id": installation_id,
                "repo_id": repo.repo_id,
                "owner": repo.owner,
                "name": repo.name,
                "full_name": repo.full_name,
                "html_url": repo.html_url,
                "description": repo.description,
                "default_branch": repo.default_branch,
                "language": repo.language,
                "topics": json.dumps(repo.topics) if repo.topics else None,
                "stargazers_count": repo.stargazers_count,
                "forks_count": repo.forks_count,
                "open_issues_count": repo.open_issues_count,
                "private": repo.private,
                "archived": repo.archived,
                "disabled": repo.disabled,
                "pushed_at": repo.pushed_at,
                "repo_created_at": repo.repo_created_at,
                "repo_updated_at": repo.repo_updated_at,
                "synced_at": now,
            }
        )
    
    upsert_stmt = insert(GitHubRepositoryModel).values(values_list)
    upsert_stmt = upsert_stmt.on_conflict_do_update(
        index_elements=["repo_id"],
        set_=_repo_upsert_set(upsert_stmt),
    )
    db.execute(upsert_stmt)

    stale_delete_stmt = delete(GitHubRepositoryModel).where(
        and_(
            GitHubRepositoryModel.installation_id == installation_id,
            ~GitHubRepositoryModel.repo_id.in_(fetched_repo_ids),
        )
    )
    stale_delete_result = db.execute(stale_delete_stmt)

    if auto_commit:
        db.commit()
    else:
        db.flush()

    return {
        "upserted": len(values_list),
        "deleted": stale_delete_result.rowcount or 0,
    }

def delete_repository(
    db: Session,
    installation_id: int,
    full_name: str,
) -> bool:
    """Repository 삭제"""
    stmt = delete(GitHubRepositoryModel).where(
        and_(
            GitHubRepositoryModel.installation_id == installation_id,
            GitHubRepositoryModel.full_name == full_name,
        )
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


def delete_installation_repositories(
    db: Session,
    installation_id: int,
) -> int:
    """Installation의 모든 Repository 삭제"""
    stmt = delete(GitHubRepositoryModel).where(
        GitHubRepositoryModel.installation_id == installation_id
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def _repo_upsert_set(stmt) -> dict:
    """Repository upsert 시 conflict 업데이트 필드"""
    return {
        "installation_id": stmt.excluded.installation_id,
        "owner": stmt.excluded.owner,
        "name": stmt.excluded.name,
        "full_name": stmt.excluded.full_name,
        "html_url": stmt.excluded.html_url,
        "description": stmt.excluded.description,
        "default_branch": stmt.excluded.default_branch,
        "language": stmt.excluded.language,
        "topics": stmt.excluded.topics,
        "stargazers_count": stmt.excluded.stargazers_count,
        "forks_count": stmt.excluded.forks_count,
        "open_issues_count": stmt.excluded.open_issues_count,
        "private": stmt.excluded.private,
        "archived": stmt.excluded.archived,
        "disabled": stmt.excluded.disabled,
        "pushed_at": stmt.excluded.pushed_at,
        "repo_created_at": stmt.excluded.repo_created_at,
        "repo_updated_at": stmt.excluded.repo_updated_at,
        "synced_at": stmt.excluded.synced_at,
    }


def _user_email_update_value(stmt):
    return func.coalesce(
        func.nullif(stmt.excluded.email, ""),
        GitHubUserModel.email,
    )


def _user_upsert_set(stmt) -> dict:
    """User upsert 시 conflict 업데이트 필드"""
    return {
        "login": stmt.excluded.login,
        "name": stmt.excluded.name,
        "email": _user_email_update_value(stmt),
        "avatar_url": stmt.excluded.avatar_url,
        "org_role": stmt.excluded.org_role,
    }


# ============================================================
# GitHub User CRUD
# ============================================================

def get_user(
    db: Session,
    database_id: int,
) -> GitHubUserModel | None:
    """User 조회 by database_id"""
    stmt = select(GitHubUserModel).where(
        GitHubUserModel.database_id == database_id
    )
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_login(
    db: Session,
    login: str,
) -> GitHubUserModel | None:
    """User 조회 by login"""
    stmt = select(GitHubUserModel).where(
        GitHubUserModel.login == login
    )
    return db.execute(stmt).scalar_one_or_none()


def upsert_users_bulk(
    db: Session,
    users_data: list[UserUpsertData],
    *,
    auto_commit: bool = True,
) -> int:
    """
    User 정보 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        users_data: User Upsert DTO 리스트

    Returns:
        Upsert된 User 수
    """
    if not users_data:
        return 0

    values_list = []
    for user in users_data:
        values_list.append({
            "database_id": user.database_id,
            "login": user.login,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "org_role": user.org_role,
        })

    stmt = insert(GitHubUserModel).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["database_id"],
        set_=_user_upsert_set(stmt),
    )

    db.execute(stmt)
    if auto_commit:
        db.commit()
    else:
        db.flush()

    return len(values_list)


def get_all_users(db: Session) -> list[GitHubUserModel]:
    """모든 User 조회"""
    stmt = select(GitHubUserModel).order_by(GitHubUserModel.login)
    return list(db.execute(stmt).scalars().all())
  
