from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from catchup.configs.config import settings

MAX_ERROR_MESSAGE_LENGTH = 2000


@dataclass(slots=True, frozen=True)
class BackfillFailureMetadata:
    last_error_type: str | None
    last_error_message: str | None
    next_retry_at: datetime | None


def truncate_error_message(
    message: str | None,
    *,
    max_length: int = MAX_ERROR_MESSAGE_LENGTH,
) -> str | None:
    if message is None:
        return None
    if len(message) <= max_length:
        return message
    return message[:max_length]


def compute_next_retry_at(now: datetime, retry_delay_minutes: int) -> datetime:
    return now + timedelta(minutes=retry_delay_minutes)


def build_failure_metadata(
    now: datetime,
    *,
    error_type: str | None,
    error_message: str | None,
    retry_delay_minutes: int | None = None,
) -> BackfillFailureMetadata:
    if error_type is None and error_message is None:
        return BackfillFailureMetadata(None, None, None)
    delay = (
        settings.VECTOR_STORE_V2_BACKFILL_FAILED_RETRY_DELAY_MINUTES
        if retry_delay_minutes is None
        else retry_delay_minutes
    )
    return BackfillFailureMetadata(
        last_error_type=error_type,
        last_error_message=truncate_error_message(error_message),
        next_retry_at=compute_next_retry_at(now, delay),
    )


def _processing_stale_after_minutes() -> int:
    return max(settings.VECTOR_STORE_V2_BACKFILL_PROCESSING_STALE_AFTER_MINUTES, 1)


def backfill_stale_processing_predicate(alias: str = "state") -> str:
    minutes = _processing_stale_after_minutes()
    return f"""
                  (
                      {alias}.processing_started_at IS NULL
                      OR {alias}.processing_started_at <= now() - make_interval(mins => {minutes})
                  )
    """


def backfill_candidate_state_predicate(alias: str = "state") -> str:
    return f"""
          AND (
              {alias}.state IS NULL
              OR {alias}.state IN ('pending', 'succeeded')
              OR (
                  {alias}.state = 'failed'
                  AND (
                      {alias}.next_retry_at IS NULL
                      OR {alias}.next_retry_at <= now()
                  )
              )
              OR (
                  {alias}.state = 'processing'
                  AND {backfill_stale_processing_predicate(alias).strip()}
              )
          )
    """


def backfill_claimable_state_predicate(
    table_name: str = "vector_store_v2_backfill_states",
) -> str:
    return f"""
            {table_name}.state IN ('pending', 'succeeded')
            OR (
                {table_name}.state = 'failed'
                AND (
                    {table_name}.next_retry_at IS NULL
                    OR {table_name}.next_retry_at <= now()
                )
            )
            OR (
                {table_name}.state = 'processing'
                AND {backfill_stale_processing_predicate(table_name).strip()}
            )
    """


def build_mark_processing_statement() -> TextClause:
    return text(
        f"""
        INSERT INTO vector_store_v2_backfill_states (
            connector,
            entity_type,
            scope_id,
            target_id,
            state,
            expected_count,
            backfill_count,
            failed_ids,
            succeeded_at,
            failed_at,
            failure_count,
            last_error_type,
            last_error_message,
            next_retry_at,
            processing_started_at
        )
        VALUES (
            :connector,
            :entity_type,
            :scope_id,
            :target_id,
            'processing',
            :expected_count,
            0,
            '[]'::jsonb,
            NULL,
            NULL,
            0,
            NULL,
            NULL,
            NULL,
            now()
        )
        ON CONFLICT (connector, entity_type, scope_id, target_id) DO UPDATE SET
            state = 'processing',
            expected_count = EXCLUDED.expected_count,
            backfill_count = 0,
            failed_ids = '[]'::jsonb,
            succeeded_at = NULL,
            failed_at = NULL,
            last_error_type = NULL,
            last_error_message = NULL,
            next_retry_at = NULL,
            processing_started_at = now()
        WHERE {backfill_claimable_state_predicate("vector_store_v2_backfill_states").strip()}
        RETURNING processing_started_at
        """
    )


def build_mark_finished_statement() -> TextClause:
    return text(
        """
        UPDATE vector_store_v2_backfill_states
        SET state = CAST(:state AS varchar(32)),
            expected_count = :expected_count,
            backfill_count = :backfill_count,
            failed_ids = CAST(:failed_ids AS jsonb),
            succeeded_at = :succeeded_at,
            failed_at = :failed_at,
            failure_count = CASE
                WHEN CAST(:state AS varchar(32)) = 'failed' THEN failure_count + 1
                ELSE 0
            END,
            last_error_type = :last_error_type,
            last_error_message = :last_error_message,
            next_retry_at = :next_retry_at,
            processing_started_at = NULL
        WHERE connector = :connector
          AND entity_type = :entity_type
          AND scope_id = :scope_id
          AND target_id = :target_id
          AND processing_started_at = :processing_started_at
        """
    )
