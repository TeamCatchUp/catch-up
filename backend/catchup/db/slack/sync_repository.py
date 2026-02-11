"""
Slack Sync State CRUD 함수

SlackSyncState 테이블에 대한 CRUD 작업 수행.
Entity Type별로 동기화 상태를 추적하고 관리.
"""

from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from catchup.db.models import (
    SlackSyncState,
    SlackChannelSyncState,
    SlackEntityType,
    SlackSyncStatus,
)


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


# ============================================================
# Channel Sync State CRUD (채널별 동기화 상태)
# ============================================================


def get_channel_sync_state(
    db: Session,
    team_id: str,
    channel_id: str,
) -> SlackChannelSyncState | None:
    """특정 채널의 동기화 상태 조회"""
    stmt = select(SlackChannelSyncState).where(
        SlackChannelSyncState.team_id == team_id,
        SlackChannelSyncState.channel_id == channel_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_all_channel_sync_states(
    db: Session,
    team_id: str,
) -> list[SlackChannelSyncState]:
    """팀의 모든 채널 동기화 상태 조회"""
    stmt = (
        select(SlackChannelSyncState)
        .where(SlackChannelSyncState.team_id == team_id)
        .order_by(SlackChannelSyncState.channel_name)
    )
    return list(db.execute(stmt).scalars().all())


def start_channel_sync(
    db: Session,
    team_id: str,
    channel_id: str,
    channel_name: str | None = None,
    oldest_ts: str | None = None,
) -> SlackChannelSyncState:
    """
    채널 동기화 시작 (상태 생성 또는 업데이트)

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        channel_id: Slack Channel ID
        channel_name: 채널명 (디버깅용)
        oldest_ts: 동기화 시작 timestamp

    Returns:
        생성 또는 업데이트된 SlackChannelSyncState
    """
    state = get_channel_sync_state(db, team_id, channel_id)
    now = datetime.now(timezone.utc)

    if state:
        # 기존 상태 업데이트
        state.last_sync_at = now
        state.last_sync_status = SlackSyncStatus.IN_PROGRESS
        state.last_sync_error = None
        if channel_name:
            state.channel_name = channel_name
        if oldest_ts is not None:
            state.oldest_ts = oldest_ts
    else:
        # 새 상태 생성
        state = SlackChannelSyncState(
            team_id=team_id,
            channel_id=channel_id,
            channel_name=channel_name,
            last_sync_at=now,
            last_sync_status=SlackSyncStatus.IN_PROGRESS,
            oldest_ts=oldest_ts,
            synced_count=0,
        )
        db.add(state)

    db.commit()
    db.refresh(state)
    return state


def update_channel_sync_progress(
    db: Session,
    team_id: str,
    channel_id: str,
    synced_count: int,
    latest_synced_ts: str | None = None,
) -> SlackChannelSyncState | None:
    """
    채널 동기화 진행 상황 업데이트 (배치 완료 시 호출)

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        channel_id: Slack Channel ID
        synced_count: 현재까지 동기화된 메시지 수
        latest_synced_ts: 마지막으로 성공한 메시지 timestamp

    Returns:
        업데이트된 SlackChannelSyncState 또는 None
    """
    state = get_channel_sync_state(db, team_id, channel_id)
    if not state:
        return None

    state.synced_count = synced_count
    if latest_synced_ts is not None:
        state.latest_synced_ts = latest_synced_ts

    db.commit()
    db.refresh(state)
    return state


def mark_channel_sync_completed(
    db: Session,
    team_id: str,
    channel_id: str,
    synced_count: int,
) -> SlackChannelSyncState | None:
    """
    채널 동기화 완료 처리

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        channel_id: Slack Channel ID
        synced_count: 최종 동기화된 메시지 수

    Returns:
        업데이트된 SlackChannelSyncState 또는 None
    """
    state = get_channel_sync_state(db, team_id, channel_id)
    if not state:
        return None

    now = datetime.now(timezone.utc)
    state.last_sync_status = SlackSyncStatus.SUCCESS
    state.last_successful_sync_at = now
    state.synced_count = synced_count
    state.last_sync_error = None

    db.commit()
    db.refresh(state)
    return state


def mark_channel_sync_failed(
    db: Session,
    team_id: str,
    channel_id: str,
    error: str,
    synced_count: int = 0,
) -> SlackChannelSyncState | None:
    """
    채널 동기화 실패 처리

    - last_successful_sync_at은 변경하지 않음 (재시도 기준점 유지)

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID
        channel_id: Slack Channel ID
        error: 에러 메시지
        synced_count: 실패 전까지 동기화된 메시지 수

    Returns:
        업데이트된 SlackChannelSyncState 또는 None
    """
    state = get_channel_sync_state(db, team_id, channel_id)
    if not state:
        return None

    state.last_sync_status = SlackSyncStatus.FAILED
    state.last_sync_error = error[:1000] if error else None
    state.synced_count = synced_count

    db.commit()
    db.refresh(state)
    return state


def delete_channel_sync_states(db: Session, team_id: str) -> int:
    """
    팀의 모든 채널 동기화 상태 삭제

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID

    Returns:
        삭제된 레코드 수
    """
    stmt = delete(SlackChannelSyncState).where(
        SlackChannelSyncState.team_id == team_id
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
