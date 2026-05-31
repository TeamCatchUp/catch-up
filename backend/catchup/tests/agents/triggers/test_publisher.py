from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from catchup.agents.triggers import publisher
from catchup.agents.triggers.publisher import _run_async
from catchup.agents.triggers.publisher import debounce_ttl_key
from catchup.agents.triggers.publisher import publish_agent_trigger_outbox
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerOutboxStatus
from catchup.db.models import AgentTriggerRun


async def _value():
    return "ok"


def test_run_async_returns_value_without_running_loop() -> None:
    assert _run_async(_value()) == "ok"


@pytest.mark.asyncio
async def test_run_async_returns_value_with_running_loop() -> None:
    assert _run_async(_value()) == "ok"


def test_debounce_ttl_key_carries_run_id_and_dispatch_token() -> None:
    assert (
        debounce_ttl_key(run_id=123, dispatch_token="token-1")
        == "agent_trigger:debounce:123:token-1"
    )


def test_publish_agent_trigger_outbox_marks_failed_when_stream_publish_fails() -> None:
    outbox = SimpleNamespace(
        id=5,
        run_id=10,
        trigger_id=1,
        agent_spec_id=101,
        event_id="event-1",
        status=AgentTriggerOutboxStatus.PENDING,
        last_error=None,
    )
    run = SimpleNamespace(
        id=10,
        policy_kind="immediate",
        dispatch_token="token-1",
    )
    db = Mock()

    def get_model(model, _id):
        if model is AgentTriggerRun:
            return run
        if model is AgentTriggerOutbox:
            return outbox
        return None

    db.get.side_effect = get_model

    def fail_publish(coro):
        coro.close()
        raise RuntimeError("redis down")

    with (
        patch(
            f"{publisher.__name__}._claim_outbox_for_publish",
            return_value=outbox,
        ),
        patch(f"{publisher.__name__}._claim_run_for_request", return_value=True),
        patch(f"{publisher.__name__}._run_async", side_effect=fail_publish),
    ):
        result = publish_agent_trigger_outbox(db=db, outbox_id=outbox.id)

    assert result is False
    assert outbox.status == AgentTriggerOutboxStatus.FAILED
    assert outbox.last_error == "redis down"
    db.rollback.assert_called_once()
    assert db.commit.call_count == 2
