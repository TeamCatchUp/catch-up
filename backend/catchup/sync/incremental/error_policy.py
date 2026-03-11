from __future__ import annotations

import asyncio

import httpx
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from catchup.connectors.base import ConnectorApiError, RateLimitError
from catchup.sync.common.exceptions import RedisStreamInitializationError, RedisStreamPublishError, SyncInternalError


def is_retryable_incremental_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            asyncio.TimeoutError,
            TimeoutError,
            httpx.TimeoutException,
            RateLimitError,
            RedisConnectionError,
            RedisTimeoutError,
            RedisStreamInitializationError,
            RedisStreamPublishError,
            SyncInternalError,
            OperationalError,
            InterfaceError,
        ),
    ):
        return True

    if isinstance(exc, DBAPIError):
        return bool(exc.connection_invalidated)

    if isinstance(exc, RedisError):
        return True

    if isinstance(exc, ConnectorApiError):
        return exc.status_code is None or int(exc.status_code) >= 500

    return False
