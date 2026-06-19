from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

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


def backfill_candidate_state_predicate(alias: str = "state") -> str:
    return f"""
          AND (
              {alias}.state IS NULL
              OR {alias}.state IN ('pending', 'succeeded')
              OR (
                  {alias}.state = 'failed'
                  AND {alias}.next_retry_at <= now()
              )
          )
    """
