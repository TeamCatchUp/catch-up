"""
Slack Sync State CRUD 함수

SlackSyncState 테이블에 대한 CRUD 작업 수행.
Entity Type별로 동기화 상태를 추적하고 관리.
"""

from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from catchup.db.models import SlackSyncState, SlackEntityType, SlackSyncStatus


def get_sync_state(
    db: Session,
    team_id: str,
    entity_type: SlackEntityType,
) -> SlackSyncState | None:
    """특정 entity_type의 동기화 상태 조회"""
    stmt = select(SlackSyncState).where(
        SlackSyncState.team_id == team_id,
        SlackSyncState.entity_type == entity_type,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_all_sync_states(db: Session, team_id: str) -> list[SlackSyncState]:
    """팀의 모든 동기화 상태 조회"""
    stmt = (
        select(SlackSyncState)
        .where(SlackSyncState.team_id == team_id)
        .order_by(SlackSyncState.entity_type)
    )
    return list(db.execute(stmt).scalars().all())


def create_or_update_sync_state(
    db: Session,
    team_id: str,
    entity_type: SlackEntityType,
    status: SlackSyncStatus,
    synced_count: int = 0,
    total_count: int = 0,
    error: str | None = None,
    oldest_ts: str | None = None,
    latest_ts: str | None = None,
) -> SlackSyncState:
    """
    동기화 상태 생성 또는 업데이트 (Upsert)

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        entity_type: 동기화 엔티티 타입
        status: 동기화 상태
        synced_count: 동기화 완료된 엔티티 수
        total_count: 동기화 대상 총 엔티티 수
        error: 에러 메시지 (실패 시)
        oldest_ts: 동기화 시작 Slack timestamp
        latest_ts: 동기화 종료 Slack timestamp

    Returns:
        생성 또는 업데이트된 SlackSyncState
    """
    state = get_sync_state(db, team_id, entity_type)
    now = datetime.now(timezone.utc)

    if state:
        # 기존 상태 업데이트
        state.last_sync_at = now
        state.last_sync_status = status
        state.synced_entities = synced_count
        state.total_entities = total_count
        state.last_sync_error = error

        if status == SlackSyncStatus.SUCCESS:
            state.last_successful_sync_at = now

        if oldest_ts is not None:
            state.oldest_ts = oldest_ts
        if latest_ts is not None:
            state.latest_ts = latest_ts
    else:
        # 새 상태 생성
        state = SlackSyncState(
            team_id=team_id,
            entity_type=entity_type,
            last_sync_at=now,
            last_sync_status=status,
            synced_entities=synced_count,
            total_entities=total_count,
            last_sync_error=error,
            last_successful_sync_at=now if status == SlackSyncStatus.SUCCESS else None,
            oldest_ts=oldest_ts,
            latest_ts=latest_ts,
        )
        db.add(state)

    db.commit()
    db.refresh(state)
    return state


def update_sync_progress(
    db: Session,
    team_id: str,
    entity_type: SlackEntityType,
    synced_count: int,
    total_count: int | None = None,
) -> SlackSyncState | None:
    """
    동기화 진행 상황 업데이트

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        entity_type: 동기화 엔티티 타입
        synced_count: 현재까지 동기화된 엔티티 수
        total_count: 전체 엔티티 수 (변경 시)

    Returns:
        업데이트된 SlackSyncState 또는 None (존재하지 않는 경우)
    """
    state = get_sync_state(db, team_id, entity_type)
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
    team_id: str,
    entity_type: SlackEntityType,
    synced_count: int,
) -> SlackSyncState | None:
    """
    동기화 완료 처리

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        entity_type: 동기화 엔티티 타입
        synced_count: 최종 동기화된 엔티티 수

    Returns:
        업데이트된 SlackSyncState 또는 None
    """
    state = get_sync_state(db, team_id, entity_type)
    if not state:
        return None

    now = datetime.now(timezone.utc)
    state.last_sync_status = SlackSyncStatus.SUCCESS
    state.last_successful_sync_at = now
    state.synced_entities = synced_count
    state.last_sync_error = None

    db.commit()
    db.refresh(state)
    return state


def mark_sync_failed(
    db: Session,
    team_id: str,
    entity_type: SlackEntityType,
    error: str,
    synced_count: int = 0,
) -> SlackSyncState | None:
    """
    동기화 실패 처리

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        entity_type: 동기화 엔티티 타입
        error: 에러 메시지
        synced_count: 실패 전까지 동기화된 엔티티 수

    Returns:
        업데이트된 SlackSyncState 또는 None
    """
    state = get_sync_state(db, team_id, entity_type)
    if not state:
        return None

    state.last_sync_status = SlackSyncStatus.FAILED
    state.last_sync_error = error[:1000] if error else None  # 1000자 제한
    state.synced_entities = synced_count

    db.commit()
    db.refresh(state)
    return state


def delete_sync_states(db: Session, team_id: str) -> int:
    """
    팀의 모든 동기화 상태 삭제

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID

    Returns:
        삭제된 레코드 수
    """
    stmt = delete(SlackSyncState).where(SlackSyncState.team_id == team_id)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
