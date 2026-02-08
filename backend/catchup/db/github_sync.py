"""
GitHub Sync State CRUD 함수

GitHubSyncState 테이블에 대한 CRUD 작업 수행.
Installation ID + Repository별로 Entity Type별 동기화 상태를 추적하고 관리.
"""

from datetime import datetime, timezone

from sqlalchemy import select, delete, and_
from sqlalchemy.orm import Session

from catchup.db.models import GitHubSyncState, GitHubEntityType, GitHubSyncStatus


def get_sync_state(
    db: Session,
    installation_id: int,
    repository_full_name: str,
    entity_type: GitHubEntityType,
) -> GitHubSyncState | None:
    """특정 repository의 entity_type 동기화 상태 조회"""
    stmt = select(GitHubSyncState).where(
        and_(
            GitHubSyncState.installation_id == installation_id,
            GitHubSyncState.repository_full_name == repository_full_name,
            GitHubSyncState.entity_type == entity_type,
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_repo_sync_states(
    db: Session,
    installation_id: int,
    repository_full_name: str,
) -> list[GitHubSyncState]:
    """Repository의 모든 동기화 상태 조회"""
    stmt = (
        select(GitHubSyncState)
        .where(
            and_(
                GitHubSyncState.installation_id == installation_id,
                GitHubSyncState.repository_full_name == repository_full_name,
            )
        )
        .order_by(GitHubSyncState.entity_type)
    )
    return list(db.execute(stmt).scalars().all())


def get_installation_sync_states(
    db: Session,
    installation_id: int,
) -> list[GitHubSyncState]:
    """Installation의 모든 동기화 상태 조회"""
    stmt = (
        select(GitHubSyncState)
        .where(GitHubSyncState.installation_id == installation_id)
        .order_by(GitHubSyncState.repository_full_name, GitHubSyncState.entity_type)
    )
    return list(db.execute(stmt).scalars().all())


def create_or_update_sync_state(
    db: Session,
    installation_id: int,
    repository_full_name: str,
    entity_type: GitHubEntityType,
    status: GitHubSyncStatus,
    synced_count: int = 0,
    total_count: int = 0,
    error: str | None = None,
) -> GitHubSyncState:
    """
    동기화 상태 생성 또는 업데이트 (Upsert)

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repository_full_name: Repository full name (owner/repo)
        entity_type: 동기화 엔티티 타입
        status: 동기화 상태
        synced_count: 동기화 완료된 엔티티 수
        total_count: 동기화 대상 총 엔티티 수
        error: 에러 메시지 (실패 시)

    Returns:
        생성 또는 업데이트된 GitHubSyncState
    """
    state = get_sync_state(db, installation_id, repository_full_name, entity_type)
    now = datetime.now(timezone.utc)

    if state:
        # 기존 상태 업데이트
        state.last_sync_at = now
        state.last_sync_status = status
        state.synced_entities = synced_count
        state.total_entities = total_count
        state.last_sync_error = error

        if status == GitHubSyncStatus.SUCCESS:
            state.last_successful_sync_at = now
    else:
        # 새 상태 생성
        state = GitHubSyncState(
            installation_id=installation_id,
            repository_full_name=repository_full_name,
            entity_type=entity_type,
            last_sync_at=now,
            last_sync_status=status,
            synced_entities=synced_count,
            total_entities=total_count,
            last_sync_error=error,
            last_successful_sync_at=now if status == GitHubSyncStatus.SUCCESS else None,
        )
        db.add(state)

    db.commit()
    db.refresh(state)
    return state


def update_sync_progress(
    db: Session,
    installation_id: int,
    repository_full_name: str,
    entity_type: GitHubEntityType,
    synced_count: int,
    total_count: int | None = None,
) -> GitHubSyncState | None:
    """
    동기화 진행 상황 업데이트

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repository_full_name: Repository full name (owner/repo)
        entity_type: 동기화 엔티티 타입
        synced_count: 현재까지 동기화된 엔티티 수
        total_count: 전체 엔티티 수 (변경 시)

    Returns:
        업데이트된 GitHubSyncState 또는 None (존재하지 않는 경우)
    """
    state = get_sync_state(db, installation_id, repository_full_name, entity_type)
    if not state:
        return None

    state.synced_entities = synced_count
    if total_count is not None:
        state.total_entities = total_count

    db.commit()
    db.refresh(state)
    return state


def mark_sync_completed(
    db: Session,
    installation_id: int,
    repository_full_name: str,
    entity_type: GitHubEntityType,
    synced_count: int,
) -> GitHubSyncState | None:
    """
    동기화 완료 처리

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repository_full_name: Repository full name (owner/repo)
        entity_type: 동기화 엔티티 타입
        synced_count: 최종 동기화된 엔티티 수

    Returns:
        업데이트된 GitHubSyncState 또는 None
    """
    state = get_sync_state(db, installation_id, repository_full_name, entity_type)
    if not state:
        return None

    now = datetime.now(timezone.utc)
    state.last_sync_status = GitHubSyncStatus.SUCCESS
    state.last_successful_sync_at = now
    state.synced_entities = synced_count
    state.last_sync_error = None

    db.commit()
    db.refresh(state)
    return state


def mark_sync_failed(
    db: Session,
    installation_id: int,
    repository_full_name: str,
    entity_type: GitHubEntityType,
    error: str,
    synced_count: int = 0,
) -> GitHubSyncState | None:
    """
    동기화 실패 처리

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repository_full_name: Repository full name (owner/repo)
        entity_type: 동기화 엔티티 타입
        error: 에러 메시지
        synced_count: 실패 전까지 동기화된 엔티티 수

    Returns:
        업데이트된 GitHubSyncState 또는 None
    """
    state = get_sync_state(db, installation_id, repository_full_name, entity_type)
    if not state:
        return None

    state.last_sync_status = GitHubSyncStatus.FAILED
    state.last_sync_error = error[:1000] if error else None  # 1000자 제한
    state.synced_entities = synced_count

    db.commit()
    db.refresh(state)
    return state


def delete_repo_sync_states(
    db: Session,
    installation_id: int,
    repository_full_name: str,
) -> int:
    """
    Repository의 모든 동기화 상태 삭제

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID
        repository_full_name: Repository full name (owner/repo)

    Returns:
        삭제된 레코드 수
    """
    stmt = delete(GitHubSyncState).where(
        and_(
            GitHubSyncState.installation_id == installation_id,
            GitHubSyncState.repository_full_name == repository_full_name,
        )
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def delete_installation_sync_states(
    db: Session,
    installation_id: int,
) -> int:
    """
    Installation의 모든 동기화 상태 삭제

    Args:
        db: SQLAlchemy Session
        installation_id: GitHub App Installation ID

    Returns:
        삭제된 레코드 수
    """
    stmt = delete(GitHubSyncState).where(
        GitHubSyncState.installation_id == installation_id
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
