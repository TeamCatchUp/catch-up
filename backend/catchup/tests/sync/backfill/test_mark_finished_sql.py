from __future__ import annotations

from catchup.sync.backfill.state import (
    build_mark_finished_statement as build_shared_mark_finished_statement,
)
from catchup.sync.backfill.state import (
    build_mark_processing_statement as build_shared_mark_processing_statement,
)
from catchup.sync.backfill.state import decide_backfill_completion
from catchup.sync.backfill.state import truncate_error_type


def test_mark_finished_statement_casts_reused_state_parameter() -> None:
    sql = str(build_shared_mark_finished_statement())

    assert "state = CAST(:state AS varchar(32))" in sql
    assert "WHEN CAST(:state AS varchar(32)) = 'failed'" in sql
    assert "failed_ids = CAST(:failed_ids AS jsonb)" in sql
    assert "processing_started_at = NULL" in sql
    assert "AND processing_started_at = :processing_started_at" in sql


def test_mark_processing_statement_claims_scope_target_conditionally() -> None:
    statement = str(build_shared_mark_processing_statement())

    assert "ON CONFLICT (connector, entity_type, scope_id, target_id)" in statement
    assert "state = 'processing'" in statement
    assert "expected_count = EXCLUDED.expected_count" in statement
    assert "failed_ids = '[]'::jsonb" in statement
    assert "processing_started_at = now()" in statement
    assert "failure_count = 0" not in statement.split(
        "ON CONFLICT (connector, entity_type, scope_id, target_id) DO UPDATE SET"
    )[1]
    assert "vector_store_v2_backfill_states.state IN ('pending', 'succeeded')" in statement
    assert "vector_store_v2_backfill_states.next_retry_at IS NULL" in statement
    assert "vector_store_v2_backfill_states.next_retry_at <= now()" in statement
    assert "vector_store_v2_backfill_states.processing_started_at IS NULL" in statement
    assert "RETURNING processing_started_at" in statement


def test_completion_decision_fails_when_processed_count_is_less_than_pending() -> None:
    decision = decide_backfill_completion(
        pending_count=2,
        backfill_count=1,
        failed_ids=[],
    )

    assert decision.state == "failed"
    assert decision.error_type == "IncompleteBackfillTarget"


def test_completion_decision_succeeds_when_processed_count_matches_pending() -> None:
    decision = decide_backfill_completion(
        pending_count=2,
        backfill_count=2,
        failed_ids=[],
    )

    assert decision.state == "succeeded"
    assert decision.error_type is None


def test_completion_decision_fails_when_failed_ids_exist() -> None:
    decision = decide_backfill_completion(
        pending_count=2,
        backfill_count=1,
        failed_ids=["github:pr:TeamCatchUp/CatchUp:724"],
    )

    assert decision.state == "failed"
    assert decision.error_type == "PartialBackfillFailure"


def test_truncate_error_type_matches_state_column_length() -> None:
    assert truncate_error_type("x" * 300) == "x" * 255
