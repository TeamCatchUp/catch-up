from datetime import datetime
from datetime import timezone

from catchup.agents.triggers.events import AgentWebhookEvent


def test_agent_webhook_event_carries_normalized_webhook_envelope() -> None:
    event = AgentWebhookEvent(
        event_id="channel_talk:user_chat.message_created:evt-1",
        external_event_id="evt-1",
        source="channel_talk",
        event_type="user_chat.message_created",
        workspace_id=1,
        occurred_at=datetime(2026, 5, 28, 1, 0, tzinfo=timezone.utc),
        payload={"entity": {"channelId": "ch-001"}},
    )

    assert event.event_id == "channel_talk:user_chat.message_created:evt-1"
    assert event.payload["entity"]["channelId"] == "ch-001"
    assert event.received_at.tzinfo is not None
