"""
Confluence Sync State CRUD 함수

ConfluenceSyncState 테이블에 대한 CRUD 작업 수행.
(cloud_id, space_key, entity_type) 단위로 동기화 상태를 추적하고 관리.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import (
    ConfluenceEntityType,
    ConfluenceSyncState,
    ConfluenceSyncStatus,
)


def get_sync_state(
    db: Session,
    cloud_id: str,
    space_key: str,
    entity_type: ConfluenceEntityType,
) -> ConfluenceSyncState | None:
    """특정 (cloud_id, space_key, entity_type)의 동기화 상태 조회"""
    stmt = select(ConfluenceSyncState).where(
        ConfluenceSyncState.cloud_id == cloud_id,
        ConfluenceSyncState.space_key == space_key,
        ConfluenceSyncState.entity_type == entity_type,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_all_sync_states(
    db: Session,
    cloud_id: str,
) -> list[ConfluenceSyncState]:
    """cloud_id의 모든 동기화 상태 조회"""
    stmt = (
        select(ConfluenceSyncState)
        .where(ConfluenceSyncState.cloud_id == cloud_id)
        .order_by(ConfluenceSyncState.space_key, ConfluenceSyncState.entity_type)
    )
    return list(db.execute(stmt).scalars().all())


def mark_sync_started(
    db: Session,
    cloud_id: str,
    space_key: str,
    entity_type: ConfluenceEntityType,
    total_count: int = 0,
) -> ConfluenceSyncState:
    """동기화 시작 상태 기록 (Upsert)"""
    state = get_sync_state(db, cloud_id, space_key, entity_type)
    now = datetime.now(timezone.utc)

    if state:
        state.last_sync_at = now
        state.last_sync_status = ConfluenceSyncStatus.IN_PROGRESS
        state.last_sync_error = None
        state.total_entities = total_count
        state.synced_entities = 0
    else:
        state = ConfluenceSyncState(
            cloud_id=cloud_id,
            space_key=space_key,
            entity_type=entity_type,
            last_sync_at=now,
            last_sync_status=ConfluenceSyncStatus.IN_PROGRESS,
            total_entities=total_count,
            synced_entities=0,
        )
        db.add(state)

    db.flush()
    return state


def mark_sync_completed(
    db: Session,
    cloud_id: str,
    space_key: str,
    entity_type: ConfluenceEntityType,
    synced_count: int,
) -> ConfluenceSyncState:
    """동기화 성공 상태 기록"""
    state = get_sync_state(db, cloud_id, space_key, entity_type)
    now = datetime.now(timezone.utc)

    if not state:
        state = ConfluenceSyncState(
            cloud_id=cloud_id,
            space_key=space_key,
            entity_type=entity_type,
        )
        db.add(state)

    state.last_sync_status = ConfluenceSyncStatus.SUCCESS
    state.last_successful_sync_at = now
    state.synced_entities = synced_count
    state.last_sync_error = None

    db.flush()
    return state


def mark_sync_failed(
    db: Session,
    cloud_id: str,
    space_key: str,
    entity_type: ConfluenceEntityType,
    error: str,
) -> ConfluenceSyncState:
    """동기화 실패 상태 기록"""
    state = get_sync_state(db, cloud_id, space_key, entity_type)

    if not state:
        state = ConfluenceSyncState(
            cloud_id=cloud_id,
            space_key=space_key,
            entity_type=entity_type,
        )
        db.add(state)

    state.last_sync_status = ConfluenceSyncStatus.FAILED
    state.last_sync_error = error[:1000] if len(error) > 1000 else error

    db.flush()
    return state


def create_or_update_sync_state(
    db: Session,
    cloud_id: str,
    space_key: str,
    entity_type: ConfluenceEntityType,
    status: ConfluenceSyncStatus,
    synced_count: int = 0,
    total_count: int = 0,
    error: str | None = None,
) -> ConfluenceSyncState:
    """동기화 상태 생성 또는 업데이트 (범용 Upsert)"""
    state = get_sync_state(db, cloud_id, space_key, entity_type)
    now = datetime.now(timezone.utc)

    if state:
        state.last_sync_at = now
        state.last_sync_status = status
        state.synced_entities = synced_count
        state.total_entities = total_count
        state.last_sync_error = error
        if status == ConfluenceSyncStatus.SUCCESS:
            state.last_successful_sync_at = now
    else:
        state = ConfluenceSyncState(
            cloud_id=cloud_id,
            space_key=space_key,
            entity_type=entity_type,
            last_sync_at=now,
            last_sync_status=status,
            synced_entities=synced_count,
            total_entities=total_count,
            last_sync_error=error,
            last_successful_sync_at=now if status == ConfluenceSyncStatus.SUCCESS else None,
        )
        db.add(state)

    db.flush()
    return state
