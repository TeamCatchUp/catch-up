from types import SimpleNamespace
from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from catchup.agents.triggers import resolver
from catchup.agents.triggers.events import AgentTriggerMatch
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.events import VerifiedConnectorWebhookEvent
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_PRIMARY
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_RESET
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_START
from catchup.db.agent_triggers import AgentTriggerEventCandidate
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTriggerRunStatus


def _trigger(
    *,
    id: int,
    condition: dict,
    event_type: str = "user_chat.new_message",
    trigger_type: str = "webhook",
    source: str = "channel_talk",
    agent_status: AgentStatus = AgentStatus.ACTIVE,
    agent_workspace_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        agent_spec_id=id + 100,
        condition=condition,
        workspace_id=1,
        type=trigger_type,
        source=source,
        event_type=event_type,
        agent_spec=SimpleNamespace(
            id=id + 100,
            status=agent_status,
            workspace_id=agent_workspace_id,
        ),
    )


def _event(
    *,
    event_type: str = "user_chat.new_message",
    payload: dict | None = None,
) -> AgentWebhookEvent:
    if payload is None and event_type == "user_chat.created":
        payload = {
            "event": "push",
            "type": "userChat",
            "entity": {
                "id": "chat-1",
                "channelId": "ch-001",
            },
        }
    elif payload is None:
        payload = {
            "event": "push",
            "type": "message",
            "entity": {
                "channelId": "ch-001",
                "chatType": "userChat",
                "chatId": "chat-1",
                "id": "msg-1",
            },
        }
    return AgentWebhookEvent(
        event_id=f"channel_talk:{event_type}:evt-1",
        source="channel_talk",
        event_type=event_type,
        payload=payload,
    )


def _candidate(trigger: object, *roles: str) -> AgentTriggerEventCandidate:
    return AgentTriggerEventCandidate(
        trigger=trigger,
        roles=frozenset(roles),
    )


def _immediate_condition(channel_id: str = "ch-001") -> dict:
    return {
        "kind": "immediate",
        "where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": channel_id,
                },
            ],
        },
    }


def _debounce_condition() -> dict:
    channel_where = {
        "all": [
            {
                "path": "$.payload.entity.channelId",
                "op": "eq",
                "value": "ch-001",
            },
        ],
    }
    return {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": 300,
        "where": channel_where,
        "reset_where": channel_where,
    }


def _debounce_match(
    *,
    event_type: str = "user_chat.created",
    reset: bool = False,
) -> AgentTriggerMatch:
    trigger = _trigger(
        id=1,
        event_type="user_chat.created",
        condition=_debounce_condition(),
    )
    policy = resolver.DebouncePolicy.model_validate(_debounce_condition())
    return AgentTriggerMatch(
        trigger_id=trigger.id,
        agent_spec_id=trigger.agent_spec_id,
        event=_event(event_type=event_type),
        policy_kind=policy.kind,
        policy=policy.model_dump(mode="json"),
        entity_key="chat-1",
        reset=reset,
    )


def test_resolve_trigger_matches_evaluates_immediate_where_clause() -> None:
    matching = _trigger(id=1, condition=_immediate_condition("ch-001"))
    non_matching = _trigger(id=2, condition=_immediate_condition("ch-002"))

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[
            _candidate(matching, TRIGGER_EVENT_ROLE_PRIMARY),
            _candidate(non_matching, TRIGGER_EVENT_ROLE_PRIMARY),
        ],
    ) as get_candidates:
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(),
        )

    assert [match.trigger_id for match in result] == [1]
    assert result[0].policy_kind == "immediate"
    get_candidates.assert_called_once_with(
        ANY,
        source="channel_talk",
        event_type="user_chat.new_message",
    )


def test_resolve_trigger_matches_skips_invalid_policy() -> None:
    malformed = _trigger(id=1, condition={"where": {"all": []}})

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(malformed, TRIGGER_EVENT_ROLE_PRIMARY)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(),
        )

    assert result == []


@pytest.mark.parametrize(
    "trigger",
    [
        _trigger(
            id=1,
            condition=_immediate_condition(),
            trigger_type="manual",
        ),
        _trigger(
            id=2,
            condition=_immediate_condition(),
            source="other_source",
        ),
        _trigger(
            id=3,
            condition=_immediate_condition(),
            agent_status=AgentStatus.DRAFT,
        ),
        _trigger(
            id=4,
            condition=_immediate_condition(),
            agent_workspace_id=2,
        ),
    ],
)
def test_resolve_trigger_matches_checks_subscription_candidate_eligibility(
    trigger: SimpleNamespace,
) -> None:
    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(trigger, TRIGGER_EVENT_ROLE_PRIMARY)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(),
        )

    assert result == []


def test_resolve_trigger_matches_debounce_start_extracts_entity_key() -> None:
    debounce = _trigger(
        id=1,
        event_type="user_chat.created",
        condition=_debounce_condition(),
    )

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(debounce, TRIGGER_EVENT_ROLE_START)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(event_type="user_chat.created"),
        )

    assert len(result) == 1
    assert result[0].policy_kind == "debounce"
    assert result[0].entity_key == "chat-1"
    assert result[0].reset is False


def test_resolve_trigger_matches_debounce_start_uses_subscription_role_and_policy() -> None:
    debounce = _trigger(
        id=1,
        event_type="user_chat.new_message",
        condition=_debounce_condition(),
    )

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(debounce, TRIGGER_EVENT_ROLE_START)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(event_type="user_chat.created"),
        )

    assert len(result) == 1
    assert result[0].reset is False
    assert result[0].entity_key == "chat-1"


def test_resolve_trigger_matches_debounce_reset_uses_subscription_role_and_policy() -> None:
    debounce = _trigger(
        id=1,
        event_type="user_chat.created",
        condition=_debounce_condition(),
    )

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(debounce, TRIGGER_EVENT_ROLE_RESET)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(event_type="user_chat.new_message"),
        )

    assert len(result) == 1
    assert result[0].reset is True
    assert result[0].entity_key == "chat-1"


def test_resolve_trigger_matches_debounce_does_not_start_from_stored_trigger_event_type() -> None:
    condition = _debounce_condition()
    debounce = _trigger(
        id=1,
        event_type="user_chat.new_message",
        condition=condition,
    )

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(debounce, TRIGGER_EVENT_ROLE_RESET)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(event_type="user_chat.new_message"),
        )

    assert len(result) == 1
    assert result[0].reset is True


def test_resolve_trigger_matches_skips_subscription_policy_role_mismatch() -> None:
    debounce = _trigger(
        id=1,
        event_type="user_chat.created",
        condition=_debounce_condition(),
    )

    with patch(
        f"{resolver.__name__}.get_trigger_event_subscription_candidates",
        return_value=[_candidate(debounce, TRIGGER_EVENT_ROLE_START)],
    ):
        result = resolver.resolve_trigger_matches(
            db=Mock(),
            event=_event(event_type="user_chat.new_message"),
        )

    assert result == []


def test_persist_debounce_reset_without_pending_run_is_noop() -> None:
    match = _debounce_match(event_type="user_chat.new_message", reset=True)
    db = Mock()
    db.scalar.return_value = None

    result = resolver._persist_debounce_match(db=db, match=match)

    assert result is None
    db.add.assert_not_called()


def test_persist_debounce_reuses_dispatching_active_run() -> None:
    match = _debounce_match()
    active_run = SimpleNamespace(id=7, status=AgentTriggerRunStatus.DISPATCHING)
    db = Mock()
    db.scalar.side_effect = [None, active_run]

    result = resolver._persist_debounce_match(db=db, match=match)

    assert result is active_run
    db.add.assert_not_called()


def test_persist_debounce_update_is_scoped_to_same_entity_key() -> None:
    match = _debounce_match()
    db = Mock()
    db.scalar.return_value = None

    resolver._persist_debounce_match(db=db, match=match)

    update_stmt = db.scalar.call_args.args[0]
    compiled = str(update_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "agent_trigger_runs.entity_key = 'chat-1'" in compiled


def test_handle_verified_webhook_event_propagates_persistence_failure() -> None:
    db = Mock()
    verified_event = VerifiedConnectorWebhookEvent(
        source="channel_talk",
        event_type="message",
        payload={
            "event": "push",
            "type": "message",
            "entity": {
                "channelId": "ch-001",
                "chatType": "userChat",
                "chatId": "chat-1",
                "id": "msg-1",
            },
        },
    )

    with (
        patch(f"{resolver.__name__}.SessionLocal", return_value=db),
        patch(
            f"{resolver.__name__}.handle_agent_webhook_event",
            side_effect=RuntimeError("database unavailable"),
        ),
    ):
        with pytest.raises(RuntimeError, match="database unavailable"):
            resolver.handle_verified_webhook_event(verified_event)

    db.rollback.assert_called_once()
    db.close.assert_called_once()


def test_handle_agent_webhook_event_persists_and_publishes_outbox() -> None:
    db = Mock()
    db.begin_nested.return_value = MagicMock()
    run = SimpleNamespace(id=123, status=AgentTriggerRunStatus.PENDING)

    with (
        patch(
            f"{resolver.__name__}.resolve_trigger_matches",
            return_value=[
                AgentTriggerMatch(
                    trigger_id=1,
                    agent_spec_id=101,
                    event=_event(),
                    policy_kind="immediate",
                    policy=_immediate_condition(),
                )
            ],
        ),
        patch(
            f"{resolver.__name__}._persist_immediate_match",
            return_value=run,
        ) as persist,
        patch(f"{resolver.__name__}.publish_pending_agent_trigger_outbox") as publish,
    ):
        result = resolver.handle_agent_webhook_event(db=db, event=_event())

    assert result.status == "accepted"
    assert result.run_ids == [123]
    assert result.matched_count == 1
    persist.assert_called_once()
    db.commit.assert_called_once()
    publish.assert_called_once_with(db=db)
