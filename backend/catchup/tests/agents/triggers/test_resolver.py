from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from catchup.agents.triggers import resolver
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


def _agent_spec_row(*, status: AgentStatus, id: int = 10):
    return SimpleNamespace(
        id=id,
        status=status,
        spec=_AGENT_SPEC,
        user_input_values={"tone": "kind"},
        workspace_id=1,
        user_id=2,
    )


def _trigger(
    *,
    id: int,
    status: AgentStatus = AgentStatus.ACTIVE,
    filter_condition: dict | None = None,
):
    return SimpleNamespace(
        id=id,
        filter_condition=filter_condition,
        agent_spec=_agent_spec_row(status=status, id=id + 100),
    )


def test_matches_filter_condition_requires_all_flat_keys() -> None:
    payload = {"channel_id": "ch-001", "event_type": "new_message"}

    assert resolver._matches_filter_condition(
        payload,
        {"channel_id": "ch-001", "event_type": "new_message"},
    )
    assert not resolver._matches_filter_condition(
        payload,
        {"channel_id": "ch-002"},
    )
    assert resolver._matches_filter_condition(payload, None)


def test_resolve_triggers_returns_all_matching_triggers() -> None:
    matching_first = _trigger(id=1, filter_condition={"channel_id": "ch-001"})
    non_matching = _trigger(id=2, filter_condition={"channel_id": "ch-002"})
    matching_second = _trigger(id=3, filter_condition={})

    with patch(
        f"{resolver.__name__}.get_webhook_triggers",
        return_value=[matching_first, non_matching, matching_second],
    ):
        result = resolver._resolve_triggers(
            db=Mock(),
            source="channel_talk",
            payload={"channel_id": "ch-001"},
        )

    assert result == [matching_first, matching_second]


@pytest.mark.asyncio
async def test_dispatch_webhook_runs_first_active_matching_agent() -> None:
    inactive_trigger = _trigger(
        id=1,
        status=AgentStatus.INACTIVE,
        filter_condition={"channel_id": "ch-001"},
    )
    active_trigger = _trigger(
        id=2,
        status=AgentStatus.ACTIVE,
        filter_condition={"channel_id": "ch-001"},
    )
    service = SimpleNamespace(run=AsyncMock(return_value="ok"))

    with (
        patch(
            f"{resolver.__name__}.get_webhook_triggers",
            return_value=[inactive_trigger, active_trigger],
        ),
        patch(f"{resolver.__name__}.build_agent_global_context", return_value=object()),
        patch(f"{resolver.__name__}.CatchUpKnowledgeBaseTool.bind"),
        patch(f"{resolver.__name__}.get_execution_service", return_value=service),
    ):
        result = await resolver.dispatch_webhook(
            db=Mock(),
            source="channel_talk",
            payload={"channel_id": "ch-001"},
        )

    assert result == "ok"
    service.run.assert_awaited_once()
    assert service.run.await_args.kwargs["spec_id"] == active_trigger.agent_spec.id


@pytest.mark.asyncio
async def test_dispatch_webhook_skips_when_matched_agent_is_not_active() -> None:
    inactive_trigger = _trigger(
        id=1,
        status=AgentStatus.DRAFT,
        filter_condition={"channel_id": "ch-001"},
    )
    service = SimpleNamespace(run=AsyncMock(return_value="should not run"))

    with (
        patch(
            f"{resolver.__name__}.get_webhook_triggers",
            return_value=[inactive_trigger],
        ),
        patch(f"{resolver.__name__}.get_execution_service", return_value=service),
    ):
        result = await resolver.dispatch_webhook(
            db=Mock(),
            source="channel_talk",
            payload={"channel_id": "ch-001"},
        )

    assert result is None
    service.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_webhook_skips_when_no_trigger_matches() -> None:
    trigger = _trigger(id=1, filter_condition={"channel_id": "ch-001"})
    service = SimpleNamespace(run=AsyncMock(return_value="should not run"))

    with (
        patch(
            f"{resolver.__name__}.get_webhook_triggers",
            return_value=[trigger],
        ),
        patch(f"{resolver.__name__}.get_execution_service", return_value=service),
    ):
        result = await resolver.dispatch_webhook(
            db=Mock(),
            source="channel_talk",
            payload={"channel_id": "ch-002"},
        )

    assert result is None
    service.run.assert_not_awaited()
