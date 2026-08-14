from catchup.db.models import TestKnowledgeMaintenanceSetting as SettingRow


def test_test_knowledge_maintenance_setting_schema_contract() -> None:
    table = SettingRow.__table__

    assert table.name == "test_knowledge_maintaince_settings"
    assert set(table.columns) == {
        table.c.id,
        table.c.workspace_id,
        table.c.channel_talk_credential_id,
        table.c.enabled,
        table.c.execution_anchor_at,
        table.c.interval_minutes,
        table.c.created_at,
        table.c.updated_at,
    }
    assert {
        foreign_key.target_fullname
        for foreign_key in table.foreign_keys
    } == {
        "workspaces.id",
        "channel_talk_credentials.id",
    }
    assert {
        constraint.name for constraint in table.constraints
    } >= {
        "ck_test_knowledge_maintaince_interval_positive",
        "uq_test_knowledge_maintaince_workspace_credential",
    }
