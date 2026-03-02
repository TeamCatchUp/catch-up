"""
Connector별 Sync Status 응답 공통 스키마.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConnectorSyncEntityStatus(BaseModel):
    """엔티티 단위 동기화 상태"""

    status: str | None = None
    synced_count: int = 0
    total_count: int | None = 0
    last_sync_at: str | None = None
    last_successful_sync_at: str | None = None
    error: str | None = None


class ConnectorSyncScope(BaseModel):
    """scope 단위 상태 (repo/project/space/channel)"""

    scope_id: str
    scope_name: str
    entities: dict[str, ConnectorSyncEntityStatus]


class ConnectorSyncStatusResponse(BaseModel):
    """툴별 status 조회 공통 응답"""

    source: Literal["github", "jira", "confluence", "slack"]
    target_id: str
    scopes: list[ConnectorSyncScope] = Field(default_factory=list)


def build_empty_entity_status(
    *,
    total_count: int | None = 0,
) -> ConnectorSyncEntityStatus:
    """
    고정 엔티티 키를 항상 내려주기 위한 기본 상태 객체 생성.
    """
    return ConnectorSyncEntityStatus(
        status=None,
        synced_count=0,
        total_count=total_count,
        last_sync_at=None,
        last_successful_sync_at=None,
        error=None,
    )


def build_entity_status(
    *,
    status: str | None,
    synced_count: int,
    total_count: int | None,
    last_sync_at: datetime | None,
    last_successful_sync_at: datetime | None,
    error: str | None,
) -> ConnectorSyncEntityStatus:
    """
    DB 상태 레코드를 공통 응답 포맷으로 정규화.
    """
    return ConnectorSyncEntityStatus(
        status=status,
        synced_count=synced_count,
        total_count=total_count,
        last_sync_at=last_sync_at.isoformat() if last_sync_at else None,
        last_successful_sync_at=(
            last_successful_sync_at.isoformat()
            if last_successful_sync_at
            else None
        ),
        error=error,
    )

