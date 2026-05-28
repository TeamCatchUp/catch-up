from types import SimpleNamespace
from unittest.mock import ANY
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from catchup.agents.triggers import resolver
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.db.models import AgentStatus

_AGENT_SPEC = {
    "agent_id": "agent-1",
    "name": "Support Agent",
    "trigger": {
        "type": "webhook",
        "config": {
            "source": "channel_talk",
            "filter": {"channel_id": "ch-001"},
        },
    },
    "system_prompt": {
        "role": "Answer customer questions",
        "background": "CatchUp support",
        "execution_guidelines": "Search first, then answer.",
    },
    "tools": [],
    "execution_order": [],
    "required_user_inputs": [],
}


def _agent_spec_row(*, status: AgentStatus, id: int = 10, workspace_id: int = 1):
    return SimpleNamespace(
        id=id,
        status=status,
        spec=_AGENT_SPEC,
        user_input_values={"tone": "kind"},
        workspace_id=workspace_id,
        user_id=2,
    )


def _trigger(
    *,
    id: int,
    status: AgentStatus = AgentStatus.ACTIVE,
    condition: dict | None = None,
    workspace_id: int = 1,
):
    return SimpleNamespace(
        id=id,
        condition=condition,
        workspace_id=workspace_id,
        source="channel_talk",
        event_type="user_chat.message_created",
        agent_spec=_agent_spec_row(
            status=status,
            id=id + 100,
            workspace_id=workspace_id,
        ),
    )


def _event(
    *,
    payload: dict | None = None,
) -> AgentWebhookEvent:
    return AgentWebhookEvent(
        event_id="channel_talk:user_chat.message_created:evt-1",
        external_event_id="evt-1",
        source="channel_talk",
        event_type="user_chat.message_created",
        workspace_id=1,
        payload=payload or {"channel_id": "ch-001"},
    )


def _immediate_condition(channel_id: str = "ch-001") -> dict:
    return {
        "kind": "immediate",
        "where": {
            "all": [
                {
                    "path": "$.payload.channel_id",
                    "op": "eq",
                    "value": channel_id,
                },
            ],
        },
    }


def test_resolve_triggers_returns_immediate_policy_triggers() -> None:
    immediate_first = _trigger(id=1, condition=_immediate_condition("ch-001"))
    immediate_second = _trigger(id=2, condition=_immediate_condition("ch-002"))
    immediate_without_where = _trigger(
        id=3,
        condition={"kind": "immediate", "where": {"all": []}},
    )
    debounce = _trigger(
        id=4,
        condition={
            "kind": "debounce",
            "start_event_type": "user_chat.message_created",
            "reset_event_types": ["user_chat.new_message"],
            "entity_key_path": "$.payload.entity.id",
            "reset_entity_key_path": "$.payload.entity.chatId",
            "quiet_period_seconds": 300,
        },
    )

    with patch(
        f"{resolver.__name__}.get_active_webhook_triggers",
        return_value=[
            immediate_first,
            immediate_second,
            immediate_without_where,
            debounce,
        ],
    ) as get_triggers:
        result = resolver._resolve_triggers(
            db=Mock(),
            event=_event(payload={"channel_id": "ch-001"}),
        )

    assert result == [immediate_first, immediate_second, immediate_without_where]
    get_triggers.assert_called_once_with(
        ANY,
        workspace_id=1,
        source="channel_talk",
        event_type="user_chat.message_created",
    )


def test_resolve_triggers_does_not_evaluate_where_in_phase_1() -> None:
    matching = _trigger(
        id=1,
        condition={
            "kind": "immediate",
            "where": {
                "all": [
                    {
                        "path": "$.payload.channel_id",
                        "op": "eq",
                        "value": "ch-001",
                    },
                    {
                        "path": "$.event_type",
                        "op": "eq",
                        "value": "user_chat.message_created",
                    },
                ],
            },
        },
    )
    non_matching = _trigger(
        id=2,
        condition={
            "kind": "immediate",
            "where": {
                "all": [
                    {
                        "path": "$.payload.channel_id",
                        "op": "eq",
                        "value": "ch-002",
                    },
                ],
            },
        },
    )

    with patch(
        f"{resolver.__name__}.get_active_webhook_triggers",
        return_value=[matching, non_matching],
    ):
        result = resolver._resolve_triggers(
            db=Mock(),
            event=_event(payload={"channel_id": "ch-001"}),
        )

    assert result == [matching, non_matching]


def test_resolve_triggers_ignores_condition_without_policy_kind() -> None:
    malformed = _trigger(id=1, condition={"where": {"all": []}})

    with patch(
        f"{resolver.__name__}.get_active_webhook_triggers",
        return_value=[malformed],
    ):
        result = resolver._resolve_triggers(
            db=Mock(),
            event=_event(payload={"channel_id": "ch-001"}),
        )

    assert result == []


def test_resolve_triggers_does_not_dispatch_debounce_policy_in_phase_1() -> None:
    debounce = _trigger(
        id=1,
        condition={
            "kind": "debounce",
            "start_event_type": "user_chat.message_created",
            "reset_event_types": ["user_chat.new_message"],
            "entity_key_path": "$.payload.entity.id",
            "reset_entity_key_path": "$.payload.entity.chatId",
            "quiet_period_seconds": 300,
            "where": {"all": []},
            "reset_where": {"all": []},
        },
    )

    with patch(
        f"{resolver.__name__}.get_active_webhook_triggers",
        return_value=[debounce],
    ):
        result = resolver._resolve_triggers(
            db=Mock(),
            event=_event(payload={"entity": {"id": "chat-1"}}),
        )

    assert result == []


def test_resolve_triggers_ignores_malformed_policy() -> None:
    malformed = _trigger(
        id=1,
        condition={
            "kind": "debounce",
            "start_event_type": "user_chat.message_created",
        },
    )

    with patch(
        f"{resolver.__name__}.get_active_webhook_triggers",
        return_value=[malformed],
    ):
        result = resolver._resolve_triggers(
            db=Mock(),
            event=_event(payload={"entity": {"id": "chat-1"}}),
        )

    assert result == []


@pytest.mark.asyncio
async def test_dispatch_webhook_event_runs_first_matching_agent() -> None:
    active_trigger = _trigger(
        id=2,
        status=AgentStatus.ACTIVE,
        condition=_immediate_condition("ch-001"),
    )
    service = SimpleNamespace(run=AsyncMock(return_value="ok"))

    with (
        patch(
            f"{resolver.__name__}.get_active_webhook_triggers",
            return_value=[active_trigger],
        ),
        patch(f"{resolver.__name__}.build_agent_global_context", return_value=object()),
        patch(f"{resolver.__name__}.CatchUpKnowledgeBaseTool.bind"),
        patch(f"{resolver.__name__}.get_execution_service", return_value=service),
    ):
        event = _event(payload={"channel_id": "ch-001"})
        result = await resolver.dispatch_webhook_event(
            db=Mock(),
            event=event,
        )

    assert result == "ok"
    service.run.assert_awaited_once()
    assert service.run.await_args.kwargs["spec_id"] == active_trigger.agent_spec.id
    assert service.run.await_args.kwargs["trigger_event"] == event


@pytest.mark.asyncio
async def test_dispatch_webhook_event_skips_when_workspace_does_not_match() -> None:
    trigger = _trigger(
        id=1,
        status=AgentStatus.ACTIVE,
        condition=_immediate_condition("ch-001"),
        workspace_id=2,
    )
    service = SimpleNamespace(run=AsyncMock(return_value="should not run"))

    with (
        patch(
            f"{resolver.__name__}.get_active_webhook_triggers",
            return_value=[trigger],
        ),
        patch(f"{resolver.__name__}.get_execution_service", return_value=service),
    ):
        result = await resolver.dispatch_webhook_event(
            db=Mock(),
            event=_event(payload={"channel_id": "ch-001"}),
        )

    assert result is None
    service.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_webhook_event_skips_when_no_trigger_matches() -> None:
    trigger = _trigger(
        id=1,
        condition={
            "kind": "debounce",
            "start_event_type": "user_chat.message_created",
            "reset_event_types": ["user_chat.new_message"],
            "entity_key_path": "$.payload.entity.id",
            "reset_entity_key_path": "$.payload.entity.chatId",
            "quiet_period_seconds": 300,
        },
    )
    service = SimpleNamespace(run=AsyncMock(return_value="should not run"))

    with (
        patch(
            f"{resolver.__name__}.get_active_webhook_triggers",
            return_value=[trigger],
        ),
        patch(f"{resolver.__name__}.get_execution_service", return_value=service),
    ):
        result = await resolver.dispatch_webhook_event(
            db=Mock(),
            event=_event(payload={"channel_id": "ch-001"}),
        )

    assert result is None
    service.run.assert_not_awaited()
