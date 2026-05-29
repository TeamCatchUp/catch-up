from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from catchup.agents.triggers.policies import PolicyValidationError
from catchup.db.agent_triggers import AgentTriggerDefinition
from catchup.db.agent_triggers import AgentTriggerDefinitionError
from catchup.db.agent_triggers import create_or_update_agent_trigger_from_definition
from catchup.db.agent_triggers import get_active_webhook_triggers
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus

BACKEND_DIR = Path(__file__).resolve().parents[3]
AGENT_TRIGGER_RUN_MIGRATION = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "1780020100_4c91f2a8e6b3_add_agent_trigger_runs.py"
)


class FakeSession:
    def __init__(self, *, agent_spec=None, trigger=None):
        self._scalar_results = [agent_spec, trigger]
        self.added = []
        self.flush_count = 0
        self.commit_count = 0

    def scalar(self, stmt):
        _ = stmt
        return self._scalar_results.pop(0)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1


def _assert_flush_without_commit(db: FakeSession) -> None:
    assert db.flush_count == 1
    assert db.commit_count == 0


def _agent_spec(*, id: int = 10, workspace_id: int = 1):
    return SimpleNamespace(id=id, workspace_id=workspace_id)


def _immediate_condition() -> dict:
    return {
        "kind": "immediate",
        "where": {
            "all": [
                {
                    "path": "$.payload.channel_id",
                    "op": "eq",
                    "value": "ch-001",
                },
            ],
        },
    }


def _debounce_condition() -> dict:
    return {
        "kind": "debounce",
        "start_event_type": "user_chat.created",
        "reset_event_types": ["user_chat.new_message"],
        "entity_key_path": "$.payload.entity.id",
        "reset_entity_key_path": "$.payload.entity.chatId",
        "quiet_period_seconds": 300,
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
    assert db.added == [trigger]
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
        "where": {"all": []},
        "reset_where": {"all": []},
    }


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
    assert db.added == []
    _assert_flush_without_commit(db)
    assert trigger.name == "New trigger"
    assert trigger.condition["kind"] == "debounce"
    assert trigger.concurrency_key is None


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
