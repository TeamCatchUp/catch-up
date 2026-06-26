from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.automations.config import INQUIRY_AUTOMATION_PRESET_KEY
from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus
from catchup.db.models import User
from catchup.db.models import UserWorkspace


def get_workspace_id_for_user(db: Session, user_id: int) -> int | None:
    """user_id에 해당하는 workspace_id를 반환한다. 소속 워크스페이스가 없으면 None을 반환한다."""
    row = db.scalar(
        select(UserWorkspace)
        .where(UserWorkspace.user_id == user_id)
        .order_by(UserWorkspace.joined_at.asc())
        .limit(1)
    )
    return row.workspace_id if row is not None else None


def list_inquiry_agent_specs(
    db: Session,
    workspace_id: int,
) -> list[tuple[AgentSpec, User]]:
    """워크스페이스에 등록된 inquiry automation AgentSpec과 작성자 User를 반환한다."""
    return list(
        db.execute(
            select(AgentSpec, User)
            .join(User, AgentSpec.user_id == User.id)
            .where(
                AgentSpec.workspace_id == workspace_id,
                AgentSpec.spec["preset_key"].as_string()
                == INQUIRY_AUTOMATION_PRESET_KEY,
            )
        ).all()
    )


def get_inquiry_agent_spec_for_update(
    db: Session,
    agent_spec_id: int,
    workspace_id: int,
) -> AgentSpec | None:
    """수정 잠금을 걸어 inquiry automation AgentSpec을 조회한다."""
    return db.scalar(
        select(AgentSpec)
        .where(
            AgentSpec.id == agent_spec_id,
            AgentSpec.workspace_id == workspace_id,
            AgentSpec.spec["preset_key"].as_string()
            == INQUIRY_AUTOMATION_PRESET_KEY,
        )
        .with_for_update()
    )


def upsert_inquiry_agent_spec(
    db: Session,
    *,
    agent_id: uuid.UUID,
    workspace_id: int,
    user_id: int,
    spec: dict[str, Any],
) -> AgentSpec:
    """agent_id 기준으로 AgentSpec을 upsert하고 반환한다.

    기존 row가 있으면 spec, status, user_id를 현재 요청 기준으로 갱신한다.
    없으면 신규 생성한다. flush만 수행하며 commit은 호출자가 담당한다.
    """
    agent_spec = db.scalar(
        select(AgentSpec)
        .where(AgentSpec.agent_id == agent_id)
        .with_for_update()
    )
    if agent_spec is not None:
        agent_spec.spec = spec
        agent_spec.status = AgentStatus.ACTIVE
        agent_spec.user_id = user_id
    else:
        agent_spec = AgentSpec(
            agent_id=agent_id,
            workspace_id=workspace_id,
            user_id=user_id,
            spec=spec,
            status=AgentStatus.ACTIVE,
        )
        db.add(agent_spec)
    db.flush()
    return agent_spec
