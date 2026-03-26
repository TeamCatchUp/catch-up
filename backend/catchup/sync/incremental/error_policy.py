from __future__ import annotations

from catchup.sync.common.retry_policy import is_retryable_sync_error


def is_retryable_incremental_error(exc: Exception) -> bool:
    return is_retryable_sync_error(exc)
