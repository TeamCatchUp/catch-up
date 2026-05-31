from datetime import datetime
from datetime import timedelta
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from catchup.agents.triggers import recovery
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus


def test_parse_debounce_ttl_key_ignores_non_debounce_key() -> None:
    assert recovery._parse_debounce_ttl_key("unrelated:key") is None


def test_parse_debounce_ttl_key_returns_run_id_and_signal_token() -> None:
    assert recovery._parse_debounce_ttl_key(
        "agent_trigger:debounce:123:token-1",
    ) == (123, "token-1")


def test_dispatch_due_debounce_run_creates_outbox_and_kicks_publish() -> None:
    run = SimpleNamespace(
        id=10,
        trigger_id=1,
        policy_kind="debounce",
        status=AgentTriggerRunStatus.PENDING,
        run_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        dispatch_token="token-1",
        latest_event_id="event-1",
    )
    trigger = SimpleNamespace(id=1, agent_spec_id=101)
    db = Mock()
    db.get.side_effect = lambda model, _id: {
        AgentTriggerRun: run,
        AgentTrigger: trigger,
    }.get(model)
    execute_result = Mock()
    execute_result.scalar_one_or_none.return_value = run.id
    db.execute.return_value = execute_result
    db.scalar.return_value = None

    with patch(f"{recovery.__name__}.publish_pending_agent_trigger_outbox") as publish:
        result = recovery.dispatch_due_debounce_run(
            db=db,
            run_id=run.id,
            dispatch_token="token-1",
        )

    assert result is True
    outbox = db.add.call_args.args[0]
    assert isinstance(outbox, AgentTriggerOutbox)
    assert outbox.run_id == run.id
    assert outbox.trigger_id == run.trigger_id
    assert outbox.agent_spec_id == trigger.agent_spec_id
    assert outbox.event_id == run.latest_event_id
    db.commit.assert_called_once()
    publish.assert_called_once_with(db=db)


def test_recover_stale_agent_trigger_executions_marks_visible_failure() -> None:
    db = Mock()
    execute_result = Mock(rowcount=2)
    db.execute.return_value = execute_result

    recovered = recovery.recover_stale_agent_trigger_executions(db=db)

    stmt = db.execute.call_args.args[0]
    assert "agent_trigger_execution_stale" in stmt.compile().params.values()
    assert recovered == 2
    db.commit.assert_called_once()
