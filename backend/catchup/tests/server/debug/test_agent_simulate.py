from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.agents.triggers.resolver import AgentTriggerIngressResult
from catchup.db.dependencies import get_db
from catchup.server.debug.agent_simulate import router

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = lambda: object()
client = TestClient(app)


def test_simulate_webhook_accepts_agent_webhook_event() -> None:
    with patch(
        "catchup.server.debug.agent_simulate.handle_agent_webhook_event",
        return_value=AgentTriggerIngressResult(
            status="accepted",
            run_ids=[123],
            matched_count=1,
        ),
    ) as handle_event:
        response = client.post(
            "/api/v1/debug/simulate-webhook",
            json={
                "event_id": "channel_talk:user_chat.new_message:evt-1",
                "external_event_id": "evt-1",
                "source": "channel_talk",
                "event_type": "user_chat.new_message",
                "workspace_id": 1,
                "payload": {
                    "event": "push",
                    "type": "message",
                    "entity": {
                        "channelId": "ch-001",
                        "chatType": "userChat",
                        "chatId": "chat-1",
                        "id": "msg-1",
                    },
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["status"] == "accepted"
    assert data["result"] == "123"
    assert data["run_ids"] == [123]
    assert data["event_id"] == "channel_talk:user_chat.new_message:evt-1"
    handle_event.assert_called_once()
    assert (
        handle_event.call_args.kwargs["event"].payload["entity"]["channelId"]
        == "ch-001"
    )
