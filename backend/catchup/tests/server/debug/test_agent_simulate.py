from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchup.agents.triggers.resolver import AgentTriggerIngressResult
from catchup.db.dependencies import get_db
from catchup.db.models import AgentStatus
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


def test_list_channel_talk_credentials_returns_selectable_channels() -> None:
    repository = SimpleNamespace(
        list_connections=lambda: [
            SimpleNamespace(
                channel_id="ch-001",
                channel_name="Support",
                credential_last_verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                webhook_token_configured=True,
            )
        ]
    )

    with patch(
        "catchup.server.debug.agent_simulate.ChannelTalkCredentialsRepository",
        return_value=repository,
    ):
        response = client.get("/api/v1/debug/channel-talk/credentials")

    assert response.status_code == 200
    assert response.json() == [
        {
            "channel_id": "ch-001",
            "channel_name": "Support",
            "credential_last_verified_at": "2026-01-01T00:00:00+00:00",
            "webhook_token_configured": True,
        }
    ]


def test_register_channel_talk_debounce_trigger_uses_selected_credential() -> None:
    db = SimpleNamespace(
        get=lambda model, _id: SimpleNamespace(
            id=7,
            workspace_id=3,
            status=AgentStatus.ACTIVE,
        ),
        commit=lambda: None,
        rollback=lambda: None,
    )
    app.dependency_overrides[get_db] = lambda: db
    repository = SimpleNamespace(
        get_connection=lambda channel_id: SimpleNamespace(
            channel_id=channel_id,
            channel_name="Support",
            webhook_token_configured=True,
        )
    )
    trigger = SimpleNamespace(
        id=99,
        agent_spec_id=7,
        name="Debug Channel Talk debounce - Support",
    )

    with (
        patch(
            "catchup.server.debug.agent_simulate.ChannelTalkCredentialsRepository",
            return_value=repository,
        ),
        patch(
            "catchup.server.debug.agent_simulate.create_or_update_agent_trigger_from_definition",
            return_value=trigger,
        ) as upsert_trigger,
    ):
        response = client.post(
            "/api/v1/debug/channel-talk/debounce-trigger",
            json={
                "agent_spec_id": 7,
                "channel_id": "ch-001",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["trigger_id"] == 99
    assert data["quiet_period_seconds"] == 60
    assert data["context_input_key"] == "channel_talk_user_chat_context"

    definition = upsert_trigger.call_args.args[1]
    assert definition.agent_spec_id == 7
    assert definition.workspace_id == 3
    assert definition.source == "channel_talk"
    assert definition.event_type == "user_chat.created"
    assert definition.condition["start_event_type"] == "user_chat.created"
    assert definition.condition["reset_event_types"] == ["user_chat.new_message"]
    assert definition.condition["where"]["all"][0] == {
        "path": "$.payload.entity.channelId",
        "op": "eq",
        "value": "ch-001",
    }
    app.dependency_overrides[get_db] = lambda: object()
