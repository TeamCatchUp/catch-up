from datetime import datetime
from datetime import timezone
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class AgentWebhookEvent(BaseModel):
    """Agent Trigger 판정 이전에 모든 Webhook Event를 정규화 DTO"""

    event_id: str = Field(description="내부적으로 webhook event를 식별하는 고유 ID")
    external_event_id: str | None = Field(
        default=None,
        description="각 vendor가 전달한 원본 event ID",
    )
    source: str = Field(description="connector key")
    event_type: str = Field(description="내부적으로 정규화한 webhook event type")
    workspace_id: int = Field(description="event가 속한 workspace ID")
    occurred_at: datetime | None = Field(
        default=None,
        description="Provider 기준 event 발생 시각",
    )
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="CatchUp이 event를 수신한 시각",
    )
    payload: dict[str, Any] = Field(
        description="Provider 원본 webhook payload",
    )


class AgentTriggerMatch(BaseModel):
    """AgentWebhookEvent가 등록된 trigger와 매칭된 결과."""

    trigger_id: int
    agent_spec_id: int
    event: AgentWebhookEvent
