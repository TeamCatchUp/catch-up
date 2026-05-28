from unittest.mock import Mock

from catchup.db.agent_triggers import get_active_webhook_triggers


def test_get_active_webhook_triggers_filters_by_normalized_event_fields() -> None:
    result_rows = [object()]
    scalar_result = Mock()
    scalar_result.all.return_value = result_rows
    db = Mock()
    db.scalars.return_value = scalar_result

    result = get_active_webhook_triggers(
        db,
        workspace_id=1,
        source="channel_talk",
        event_type="user_chat.message_created",
    )

    assert result == result_rows
    stmt = db.scalars.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    assert "JOIN agent_specs" in compiled
    assert "agent_triggers.type = 'webhook'" in compiled
    assert "agent_triggers.workspace_id = 1" in compiled
    assert "agent_triggers.source = 'channel_talk'" in compiled
    assert "agent_triggers.event_type = 'user_chat.message_created'" in compiled
    assert "agent_specs.status = 'active'" in compiled
