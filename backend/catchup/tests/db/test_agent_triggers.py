from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from catchup.agents.triggers.policies import PolicyValidationError
from catchup.agents.triggers.policies import parse_policy
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_PRIMARY
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_RESET
from catchup.db.agent_triggers import TRIGGER_EVENT_ROLE_START
from catchup.db.agent_triggers import AgentTriggerDefinition
from catchup.db.agent_triggers import AgentTriggerDefinitionError
from catchup.db.agent_triggers import create_or_update_agent_trigger_from_definition
from catchup.db.agent_triggers import derive_trigger_event_subscriptions
from catchup.db.agent_triggers import get_trigger_event_subscription_candidates
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerEventSubscription
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus

BACKEND_DIR = Path(__file__).resolve().parents[3]
AGENT_TRIGGER_RUN_MIGRATION = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "1780020100_4c91f2a8e6b3_add_agent_trigger_runs.py"
)
AGENT_TRIGGER_EVENT_SUBSCRIPTION_MIGRATION = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "1780100000_9e7a4b2c1d3f_add_agent_trigger_event_subscriptions.py"
)


class FakeSession:
    def __init__(self, *, agent_spec=None, trigger=None):
        self._scalar_results = [agent_spec, trigger]
        self.added = []
        self.executed = []
        self.flush_count = 0
        self.commit_count = 0

    def scalar(self, stmt):
        _ = stmt
        return self._scalar_results.pop(0)

    def add(self, row):
        self.added.append(row)

    def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(all=lambda: [])

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1


def _assert_flush_without_commit(db: FakeSession) -> None:
    assert db.flush_count == 2
    assert db.commit_count == 0


def _agent_spec(*, id: int = 10, workspace_id: int = 1):
    return SimpleNamespace(id=id, workspace_id=workspace_id)


def _immediate_condition() -> dict:
    return {
        "kind": "immediate",
        "where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "ch-001",
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
            }
        ]
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


def _definition(**overrides) -> AgentTriggerDefinition:
    values = {
        "agent_spec_id": 10,
        "workspace_id": 1,
        "name": "Support trigger",
        "source": "channel_talk",
        "event_type": "user_chat.created",
        "condition": _immediate_condition(),
        "concurrency_key": None,
    }
    values.update(overrides)
    return AgentTriggerDefinition(**values)


def test_create_or_update_agent_trigger_creates_immediate_trigger() -> None:
    db = FakeSession(agent_spec=_agent_spec(), trigger=None)

    trigger = create_or_update_agent_trigger_from_definition(
        db,
        _definition(concurrency_key=" support-room "),
    )

    assert isinstance(trigger, AgentTrigger)
    assert len(db.added) == 2
    assert db.added[0] is trigger
    subscription = db.added[1]
    assert isinstance(subscription, AgentTriggerEventSubscription)
    assert subscription.trigger is trigger
    assert subscription.source == "channel_talk"
    assert subscription.event_type == "user_chat.created"
    assert subscription.role == TRIGGER_EVENT_ROLE_PRIMARY
    _assert_flush_without_commit(db)
    assert trigger.agent_spec_id == 10
    assert trigger.workspace_id == 1
    assert trigger.name == "Support trigger"
    assert trigger.type == "webhook"
    assert trigger.source == "channel_talk"
    assert trigger.event_type == "user_chat.created"
    assert trigger.condition == _immediate_condition()
    assert trigger.concurrency_key == "support-room"


def test_create_or_update_agent_trigger_persists_debounce_canonical_defaults() -> None:
    db = FakeSession(agent_spec=_agent_spec(), trigger=None)

    trigger = create_or_update_agent_trigger_from_definition(
        db,
        _definition(
            event_type="user_chat.created",
            condition=_debounce_condition(),
        ),
    )

    assert trigger.condition == {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": 300,
        "run_context": "latest_event",
        "where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "ch-001",
                }
            ]
        },
        "reset_where": {
            "all": [
                {
                    "path": "$.payload.entity.channelId",
                    "op": "eq",
                    "value": "ch-001",
                }
            ]
        },
    }
    subscriptions = [
        row for row in db.added if isinstance(row, AgentTriggerEventSubscription)
    ]
    assert [(row.event_type, row.role) for row in subscriptions] == [
        ("user_chat.created", TRIGGER_EVENT_ROLE_START),
        ("user_chat.new_message", TRIGGER_EVENT_ROLE_RESET),
    ]


def test_create_or_update_agent_trigger_updates_existing_upsert_key() -> None:
    existing = AgentTrigger(
        agent_spec_id=10,
        workspace_id=1,
        name="Old trigger",
        type="webhook",
        source="channel_talk",
        event_type="user_chat.created",
        condition={"kind": "immediate", "where": {"all": []}},
        concurrency_key="old-key",
    )
    existing.id = 99
    db = FakeSession(agent_spec=_agent_spec(), trigger=existing)

    trigger = create_or_update_agent_trigger_from_definition(
        db,
        _definition(
            name="New trigger",
            condition=_debounce_condition(),
            concurrency_key="",
        ),
    )

    assert trigger is existing
    subscriptions = [
        row for row in db.added if isinstance(row, AgentTriggerEventSubscription)
    ]
    assert [(row.event_type, row.role) for row in subscriptions] == [
        ("user_chat.created", TRIGGER_EVENT_ROLE_START),
        ("user_chat.new_message", TRIGGER_EVENT_ROLE_RESET),
    ]
    _assert_flush_without_commit(db)
    assert trigger.name == "New trigger"
    assert trigger.condition["kind"] == "debounce"
    assert trigger.concurrency_key is None
    assert db.executed
    compiled_delete = str(db.executed[0].compile(compile_kwargs={"literal_binds": True}))
    assert "DELETE FROM agent_trigger_event_subscriptions" in compiled_delete
    assert "agent_trigger_event_subscriptions.trigger_id = 99" in compiled_delete


def test_derive_trigger_event_subscriptions_deduplicates_reset_events() -> None:
    condition = {
        **_debounce_condition(),
        "reset_event_types": [
            "user_chat.new_message",
            "user_chat.new_message",
        ],
    }

    definitions = derive_trigger_event_subscriptions(
        source="channel_talk",
        primary_event_type="legacy.primary",
        policy=parse_policy(condition),
    )

    assert [(row.event_type, row.role) for row in definitions] == [
        ("user_chat.created", TRIGGER_EVENT_ROLE_START),
        ("user_chat.new_message", TRIGGER_EVENT_ROLE_RESET),
    ]


@pytest.mark.parametrize(
    "condition",
    [
        {"channel_id": "ch-001"},
        {"kind": "unsupported"},
    ],
)
def test_create_or_update_agent_trigger_rejects_invalid_condition(condition) -> None:
    db = FakeSession(agent_spec=_agent_spec(), trigger=None)

    with pytest.raises(PolicyValidationError):
        create_or_update_agent_trigger_from_definition(
            db,
            _definition(condition=condition),
        )

    assert db.added == []
    assert db.flush_count == 0
    assert db.commit_count == 0


@pytest.mark.parametrize(
    "condition",
    [
        {"kind": "immediate", "where": {"all": []}},
        {
            "kind": "immediate",
            "where": {
                "path": "$.payload.entity.channelId",
                "op": "contains",
                "value": "ch-001",
            },
        },
        {
            **_debounce_condition(),
            "where": {"all": []},
        },
        {
            **_debounce_condition(),
            "reset_where": {"all": []},
        },
    ],
)
def test_create_or_update_agent_trigger_requires_channel_talk_channel_boundary(
    condition: dict,
) -> None:
    db = FakeSession(agent_spec=_agent_spec(), trigger=None)

    with pytest.raises(AgentTriggerDefinitionError, match="payload.entity.channelId"):
        create_or_update_agent_trigger_from_definition(
            db,
            _definition(condition=condition),
        )

    assert db.added == []
    assert db.flush_count == 0
    assert db.commit_count == 0


def test_create_or_update_agent_trigger_rejects_workspace_mismatch() -> None:
    db = FakeSession(agent_spec=_agent_spec(workspace_id=2), trigger=None)

    with pytest.raises(AgentTriggerDefinitionError):
        create_or_update_agent_trigger_from_definition(db, _definition())

    assert db.added == []
    assert db.flush_count == 0
    assert db.commit_count == 0


def test_create_or_update_agent_trigger_rejects_missing_agent_spec() -> None:
    db = FakeSession(agent_spec=None, trigger=None)

    with pytest.raises(AgentTriggerDefinitionError):
        create_or_update_agent_trigger_from_definition(db, _definition())

    assert db.added == []
    assert db.flush_count == 0
    assert db.commit_count == 0


def test_agent_trigger_model_declares_definition_upsert_constraint() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in AgentTrigger.__table__.constraints
        if constraint.name
    }

    assert constraints["uq_agent_triggers_agent_spec_source_event_type"] == (
        "agent_spec_id",
        "source",
        "event_type",
    )


def test_agent_trigger_event_subscription_model_declares_routing_contract() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in AgentTriggerEventSubscription.__table__.constraints
        if constraint.name
    }

    assert constraints["uq_agent_trigger_event_sub_role"] == (
        "trigger_id",
        "source",
        "event_type",
        "role",
    )

    indexes = {
        index.name: tuple(index.columns.keys())
        for index in AgentTriggerEventSubscription.__table__.indexes
    }
    assert indexes["idx_agent_trigger_event_sub_lookup"] == ("source", "event_type")
    assert indexes["idx_agent_trigger_event_sub_trigger_id"] == ("trigger_id",)


def test_get_trigger_event_subscription_candidates_uses_subscription_as_routing_index() -> None:
    trigger = SimpleNamespace(id=1)
    subscription_result = Mock()
    subscription_result.all.return_value = [
        (1, TRIGGER_EVENT_ROLE_START),
        (1, TRIGGER_EVENT_ROLE_RESET),
    ]
    trigger_result = Mock()
    trigger_result.all.return_value = [trigger]
    db = Mock()
    db.execute.return_value = subscription_result
    db.scalars.return_value = trigger_result

    result = get_trigger_event_subscription_candidates(
        db,
        source="channel_talk",
        event_type="user_chat.new_message",
    )

    assert len(result) == 1
    assert result[0].trigger is trigger
    assert result[0].roles == frozenset(
        {TRIGGER_EVENT_ROLE_START, TRIGGER_EVENT_ROLE_RESET}
    )
    subscription_stmt = db.execute.call_args.args[0]
    compiled_subscription = str(
        subscription_stmt.compile(compile_kwargs={"literal_binds": True})
    )

    assert "FROM agent_trigger_event_subscriptions" in compiled_subscription
    assert "JOIN" not in compiled_subscription
    assert "agent_triggers" not in compiled_subscription
    assert "agent_specs" not in compiled_subscription
    assert "agent_trigger_event_subscriptions.source = 'channel_talk'" in compiled_subscription
    assert (
        "agent_trigger_event_subscriptions.event_type = "
        "'user_chat.new_message'" in compiled_subscription
    )

    trigger_stmt = db.scalars.call_args.args[0]
    compiled_trigger = str(trigger_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "FROM agent_triggers" in compiled_trigger
    assert "agent_triggers.id IN (1)" in compiled_trigger
    assert "agent_triggers.type = 'webhook'" not in compiled_trigger
    assert "agent_triggers.source = 'channel_talk'" not in compiled_trigger
    assert "agent_specs.status" not in compiled_trigger


def test_agent_trigger_run_model_declares_runtime_constraints() -> None:
    assert "workspace_id" not in AgentTriggerRun.__table__.columns

    columns = AgentTriggerRun.__table__.columns
    assert columns["trigger_id"].nullable is False
    assert columns["policy_kind"].nullable is False
    assert columns["entity_key"].nullable is True
    assert columns["status"].nullable is False
    assert columns["run_after"].nullable is True
    assert columns["start_event_id"].nullable is False
    assert columns["latest_event_id"].nullable is False
    assert columns["dispatch_token"].nullable is False
    assert columns["policy_metadata"].nullable is False
    assert columns["last_error"].nullable is True
    assert columns["policy_metadata"].server_default is not None
    assert columns["status"].server_default is not None
    assert columns["created_at"].nullable is False
    assert columns["updated_at"].nullable is False

    indexes = {index.name: index for index in AgentTriggerRun.__table__.indexes}

    assert tuple(indexes["idx_agent_trigger_runs_due"].columns.keys()) == (
        "status",
        "run_after",
    )
    assert tuple(
        indexes["idx_agent_trigger_runs_trigger_latest_event"].columns.keys()
    ) == (
        "trigger_id",
        "latest_event_id",
    )

    unique_index = indexes["uq_agent_trigger_runs_active_trigger_entity"]
    assert unique_index.unique is True
    assert tuple(unique_index.columns.keys()) == ("trigger_id", "entity_key")
    partial_where = str(unique_index.dialect_options["postgresql"]["where"])
    assert "pending" in partial_where
    assert "dispatching" in partial_where
    assert "entity_key IS NOT NULL" in partial_where


def test_agent_trigger_run_status_values_match_runtime_lifecycle() -> None:
    assert {status.value for status in AgentTriggerRunStatus} == {
        "pending",
        "dispatching",
        "completed",
        "failed",
        "cancelled",
    }


def test_agent_trigger_run_migration_matches_schema_contract() -> None:
    migration = AGENT_TRIGGER_RUN_MIGRATION.read_text()

    assert '"agent_trigger_runs"' in migration
    assert '"workspace_id"' not in migration
    assert '"policy_metadata"' in migration
    assert "'{}'::jsonb" in migration
    assert '"idx_agent_trigger_runs_due"' in migration
    assert '["status", "run_after"]' in migration
    assert '"idx_agent_trigger_runs_trigger_latest_event"' in migration
    assert '["trigger_id", "latest_event_id"]' in migration
    assert '"uq_agent_trigger_runs_active_trigger_entity"' in migration
    assert '["trigger_id", "entity_key"]' in migration
    assert "status IN ('pending', 'dispatching') AND entity_key IS NOT NULL" in migration


def test_agent_trigger_event_subscription_migration_matches_schema_contract() -> None:
    migration = AGENT_TRIGGER_EVENT_SUBSCRIPTION_MIGRATION.read_text()

    assert '"agent_trigger_event_subscriptions"' in migration
    assert '"trigger_id"' in migration
    assert '"source"' in migration
    assert '"event_type"' in migration
    assert '"role"' in migration
    assert '"uq_agent_trigger_event_sub_role"' in migration
    assert '"idx_agent_trigger_event_sub_lookup"' in migration
    assert '["source", "event_type"]' in migration
    assert "duplicate user_chat.new_message trigger definitions exist" in migration
    assert "'user_chat.message_created'" in migration
    assert "'user_chat.new_message'" in migration
    assert '"user_chat.message_created"' in migration
    assert '"user_chat.new_message"' in migration
    assert '"$.payload.channel_id"' in migration
    assert '"$.payload.entity.channelId"' in migration
    assert "'$.payload.user_chat_id'" in migration
    assert "'$.payload.entity.id'" in migration
    assert "'$.payload.entity.chatId'" in migration
    assert '"$.payload.user_chat_id"' in migration
    assert '"$.payload.entity.id"' in migration
    assert '"$.payload.entity.chatId"' in migration
    assert "'{where}'" in migration
    assert "'{reset_where}'" in migration
    assert "condition->>'kind' = 'immediate'" in migration
    assert "condition->>'kind' = 'debounce'" in migration
    assert "condition->>'start_event_type'" in migration
    assert "jsonb_object_keys" in migration
    assert "jsonb_array_length" in migration
    assert "AND CASE" in migration
    assert "ELSE false" in migration
    assert "jsonb_typeof(condition->'quiet_period_seconds') = 'number'" in migration
    assert "jsonb_typeof(t.condition->'quiet_period_seconds') = 'number'" in migration
    assert "jsonb_array_elements_text" in migration
    assert "'primary'" in migration
    assert "'start'" in migration
    assert "'reset'" in migration
