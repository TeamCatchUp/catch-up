from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class VerifiedConnectorWebhookEvent(BaseModel):
    """Webhook Router에서 검증한 Webhook Event"""

    source: str
    event_type: str
    payload: dict[str, Any]
