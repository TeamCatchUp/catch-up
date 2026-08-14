from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import TestKnowledgeMaintenanceSetting


def list_test_knowledge_maintenance_settings(
    db: Session,
    *,
    workspace_id: int | None = None,
) -> list[TestKnowledgeMaintenanceSetting]:
    statement = select(TestKnowledgeMaintenanceSetting)
    if workspace_id is not None:
        statement = statement.where(
            TestKnowledgeMaintenanceSetting.workspace_id == workspace_id
        )
    return list(
        db.scalars(
            statement.order_by(TestKnowledgeMaintenanceSetting.id)
        )
    )


def get_test_knowledge_maintenance_setting(
    db: Session,
    *,
    setting_id: int,
) -> TestKnowledgeMaintenanceSetting | None:
    return db.get(TestKnowledgeMaintenanceSetting, setting_id)


def upsert_test_knowledge_maintenance_setting(
    db: Session,
    *,
    workspace_id: int,
    channel_talk_credential_id: int,
    enabled: bool,
    execution_anchor_at: datetime,
    interval_minutes: int,
) -> TestKnowledgeMaintenanceSetting:
    setting = db.scalar(
        select(TestKnowledgeMaintenanceSetting).where(
            TestKnowledgeMaintenanceSetting.workspace_id == workspace_id,
            TestKnowledgeMaintenanceSetting.channel_talk_credential_id
            == channel_talk_credential_id,
        )
    )
    if setting is None:
        setting = TestKnowledgeMaintenanceSetting(
            workspace_id=workspace_id,
            channel_talk_credential_id=channel_talk_credential_id,
            enabled=enabled,
            execution_anchor_at=execution_anchor_at,
            interval_minutes=interval_minutes,
        )
        db.add(setting)
    else:
        setting.enabled = enabled
        setting.execution_anchor_at = execution_anchor_at
        setting.interval_minutes = interval_minutes
    db.flush()
    return setting
