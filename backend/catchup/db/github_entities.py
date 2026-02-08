"""
GitHub Entities CRUD 함수

GitHubRepository 테이블에 대한 CRUD 작업 수행.
Installation에 연결된 Repository 정보를 관리.
"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, delete, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from catchup.db.models import GitHubRepository as GitHubRepositoryModel


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


def upsert_repository(
    db: Session,
    installation_id: int,
    repo_id: int,
    owner: str,
    name: str,
    full_name: str,
    html_url: str,
    description: str | None = None,
    default_branch: str = "main",
    language: str | None = None,
    topics: list[str] | None = None,
    stargazers_count: int = 0,
    forks_count: int = 0,
    open_issues_count: int = 0,
    private: bool = False,
    archived: bool = False,
    disabled: bool = False,
    pushed_at: datetime | None = None,
    repo_created_at: datetime | None = None,
    repo_updated_at: datetime | None = None,
) -> GitHubRepositoryModel:
    """
    Repository 정보 Upsert

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repo_id: GitHub Repository ID
        owner: Repository owner
        name: Repository name
        full_name: Full name (owner/repo)
        html_url: Repository URL
        description: Repository description
        default_branch: Default branch name
        language: Primary programming language
        topics: Repository topics
        stargazers_count: Star count
        forks_count: Fork count
        open_issues_count: Open issues count
        private: Is private repository
        archived: Is archived
        disabled: Is disabled
        pushed_at: Last push time
        repo_created_at: Repository creation time
        repo_updated_at: Repository update time

    Returns:
        Upsert된 GitHubRepository
    """
    now = datetime.now(timezone.utc)
    topics_json = json.dumps(topics) if topics else None

    values = {
        "installation_id": installation_id,
        "repo_id": repo_id,
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "html_url": html_url,
        "description": description,
        "default_branch": default_branch,
        "language": language,
        "topics": topics_json,
        "stargazers_count": stargazers_count,
        "forks_count": forks_count,
        "open_issues_count": open_issues_count,
        "private": private,
        "archived": archived,
        "disabled": disabled,
        "pushed_at": pushed_at,
        "repo_created_at": repo_created_at,
        "repo_updated_at": repo_updated_at,
        "synced_at": now,
    }

    stmt = insert(GitHubRepositoryModel).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["repo_id"],
        set_={
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
    )

    db.execute(stmt)
    db.commit()

    return get_repository_by_id(db, repo_id)


def upsert_repositories_bulk(
    db: Session,
    installation_id: int,
    repos_data: list[dict[str, Any]],
) -> int:
    """
    Repository 정보 벌크 Upsert

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repos_data: Repository 정보 리스트 (API 응답에서 파싱)

    Returns:
        Upsert된 Repository 수
    """
    if not repos_data:
        return 0

    now = datetime.now(timezone.utc)
    values_list = []

    for repo in repos_data:
        owner_data = repo.get("owner", {})
        topics = repo.get("topics", [])

        values_list.append({
            "installation_id": installation_id,
            "repo_id": _to_int(repo.get("id")),
            "owner": owner_data.get("login", ""),
            "name": repo.get("name", ""),
            "full_name": repo.get("full_name", ""),
            "html_url": repo.get("html_url", ""),
            "description": repo.get("description"),
            "default_branch": repo.get("default_branch", "main"),
            "language": repo.get("language"),
            "topics": json.dumps(topics) if topics else None,
            "stargazers_count": _to_int(repo.get("stargazers_count", 0)),
            "forks_count": _to_int(repo.get("forks_count", 0)),
            "open_issues_count": _to_int(repo.get("open_issues_count", 0)),
            "private": repo.get("private", False),
            "archived": repo.get("archived", False),
            "disabled": repo.get("disabled", False),
            "pushed_at": _parse_datetime(repo.get("pushed_at")),
            "repo_created_at": _parse_datetime(repo.get("created_at")),
            "repo_updated_at": _parse_datetime(repo.get("updated_at")),
            "synced_at": now,
        })

    stmt = insert(GitHubRepositoryModel).values(values_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["repo_id"],
        set_={
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
    )

    db.execute(stmt)
    db.commit()

    return len(values_list)


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


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """ISO 8601 문자열 또는 datetime 객체를 datetime으로 변환"""
    if value is None:
        return None
    # 이미 datetime 객체인 경우 그대로 반환
    if isinstance(value, datetime):
        return value
    # 문자열인 경우 파싱
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def _to_int(value: Any, default: int = 0) -> int:
    """값을 정수로 변환 (None이나 변환 실패 시 기본값 반환)"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
