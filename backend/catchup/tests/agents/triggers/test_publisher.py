from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from catchup.agents.triggers import publisher
from catchup.agents.triggers.publisher import debounce_ttl_key
from catchup.agents.triggers.publisher import publish_agent_trigger_outbox
from catchup.agents.triggers.publisher import schedule_debounce_wakeup
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerOutboxStatus
from catchup.db.models import AgentTriggerRun


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

    with (
        patch(
            f"{publisher.__name__}._claim_outbox_for_publish",
            return_value=outbox,
        ),
        patch(f"{publisher.__name__}._claim_run_for_request", return_value=True),
        patch(
            f"{publisher.__name__}._publish_request_sync",
            side_effect=RuntimeError("redis down"),
        ),
    ):
        result = publish_agent_trigger_outbox(db=db, outbox_id=outbox.id)

    assert result is False
    assert outbox.status == AgentTriggerOutboxStatus.FAILED
    assert outbox.last_error == "redis down"
    db.rollback.assert_called_once()
    assert db.commit.call_count == 2


def test_publish_agent_trigger_outbox_marks_published_with_stream_message_id() -> None:
    outbox = SimpleNamespace(
        id=5,
        run_id=10,
        trigger_id=1,
        agent_spec_id=101,
        event_id="event-1",
        status=AgentTriggerOutboxStatus.PENDING,
        stream_message_id=None,
        published_at=None,
        last_error="old error",
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

    with (
        patch(
            f"{publisher.__name__}._claim_outbox_for_publish",
            return_value=outbox,
        ),
        patch(f"{publisher.__name__}._claim_run_for_request", return_value=True),
        patch(
            f"{publisher.__name__}._publish_request_sync",
            return_value="stream-message-1",
        ),
    ):
        result = publish_agent_trigger_outbox(db=db, outbox_id=outbox.id)

    assert result is True
    assert outbox.status == AgentTriggerOutboxStatus.PUBLISHED
    assert outbox.stream_message_id == "stream-message-1"
    assert outbox.published_at is not None
    assert outbox.last_error is None
    assert db.commit.call_count == 2


def test_schedule_debounce_wakeup_uses_sync_ttl_writer() -> None:
    run = SimpleNamespace(
        id=123,
        trigger_id=5,
        entity_key="chat-1",
        dispatch_token="token-1",
        run_after=publisher.datetime.now(publisher.timezone.utc)
        + publisher.timedelta(seconds=30),
    )

    with patch(f"{publisher.__name__}._set_debounce_ttl_sync") as set_ttl:
        schedule_debounce_wakeup(run)

    set_ttl.assert_called_once()
    _, kwargs = set_ttl.call_args
    assert kwargs["key"] == "agent_trigger:debounce:123:token-1"
    assert kwargs["seconds"] >= 1
    assert '"run_id":123' in kwargs["value"]
