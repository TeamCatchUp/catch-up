from unittest.mock import AsyncMock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.db.dependencies import get_db
from catchup.server.debug.agent_simulate import router

app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = lambda: object()
client = TestClient(app)


def test_simulate_webhook_accepts_agent_webhook_event() -> None:
    with patch(
        "catchup.server.debug.agent_simulate.dispatch_webhook_event",
        new=AsyncMock(return_value="ok"),
    ) as dispatch:
        response = client.post(
            "/api/v1/debug/simulate-webhook",
            json={
                "event_id": "channel_talk:user_chat.message_created:evt-1",
                "external_event_id": "evt-1",
                "source": "channel_talk",
                "event_type": "user_chat.message_created",
                "workspace_id": 1,
                "payload": {"channel_id": "ch-001"},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["result"] == "ok"
    assert data["event_id"] == "channel_talk:user_chat.message_created:evt-1"
    dispatch.assert_awaited_once()
    assert dispatch.await_args.kwargs["event"].payload["channel_id"] == "ch-001"
