from catchup.db.models import VectorStoreV2BackfillState


def test_vector_store_v2_backfill_state_model_declares_retry_state_columns() -> None:
    table = VectorStoreV2BackfillState.__table__

    assert table.name == "vector_store_v2_backfill_states"
    constraint_names = {constraint.name for constraint in table.constraints}
    assert "uq_vector_store_v2_backfill_states_scope_target" in constraint_names
    assert {
        "connector",
        "entity_type",
        "scope_id",
        "target_id",
        "state",
        "expected_count",
        "backfill_count",
        "failed_ids",
        "succeeded_at",
        "failed_at",
        "failure_count",
        "last_error_type",
        "last_error_message",
        "next_retry_at",
    }.issubset(set(table.c.keys()))

    index_names = {index.name for index in table.indexes}
    assert "ix_vector_store_v2_backfill_states_lookup" in index_names
    assert "ix_vector_store_v2_backfill_states_retry_lookup" in index_names
