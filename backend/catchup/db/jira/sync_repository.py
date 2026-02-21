"""
Jira Sync State CRUD 함수

JiraSyncState 테이블에 대한 CRUD 작업 수행.
Entity Type별로 동기화 상태를 추적하고 관리.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import JiraEntityType, JiraSyncState, JiraSyncStatus


def get_sync_state(
    db: Session,
    cloud_id: str,
    entity_type: JiraEntityType,
    project_key: str | None = None
) -> JiraSyncState | None:
    """특정 entity_type의 동기화 상태 조회"""
    stmt = select(JiraSyncState).where(
        JiraSyncState.cloud_id == cloud_id,
        JiraSyncState.entity_type == entity_type,
        JiraSyncState.project_key == project_key,
    )
    return db.execute(stmt).scalar_one_or_none()


def create_or_update_sync_state(
    db: Session,
    cloud_id: str,
    entity_type: JiraEntityType,
    status: JiraSyncStatus,
    project_key: str | None = None,
    synced_count: int = 0,
    total_count: int = 0,
    error: str | None = None,
) -> JiraSyncState:
    """동기화 상태 생성 또는 업데이트 (Upsert)"""
    state = get_sync_state(db, cloud_id, entity_type, project_key)
    now = datetime.now(timezone.utc)

    if state:
        state.last_sync_at = now
        state.last_sync_status = status
        state.synced_entities = synced_count
        state.total_entities = total_count
        state.last_sync_error = error
        if status == JiraSyncStatus.SUCCESS:
            state.last_successful_sync_at = now
    else:
        state = JiraSyncState(
            cloud_id=cloud_id,
            entity_type=entity_type,
            project_key=project_key,
            last_sync_at=now,
            last_sync_status=status,
            synced_entities=synced_count,
            total_entities=total_count,
            last_sync_error=error,
            last_successful_sync_at=now if status == JiraSyncStatus.SUCCESS else None,
        )
        db.add(state)

    db.commit()
    db.refresh(state)
    return state
