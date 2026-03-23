from __future__ import annotations

import asyncio
import random
from datetime import timedelta

import httpx
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import InterfaceError
from sqlalchemy.exc import OperationalError

from catchup.connectors.base.exceptions import ConnectorApiError
from catchup.connectors.base.exceptions import RateLimitError
from catchup.sync.common.exceptions import RedisStreamInitializationError
from catchup.sync.common.exceptions import RedisStreamPublishError
from catchup.sync.common.exceptions import SyncInternalError


def is_retryable_sync_error(exc: Exception) -> bool:
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

            # DB Internal Error
            OperationalError,
            InterfaceError,
        ),
    ):
        return True

    # DB가 반환한 에러 중 Connection 관련 문제가 아닌 경우
    if isinstance(exc, DBAPIError):
        return bool(exc.connection_invalidated)

    if isinstance(exc, RedisError):
        return True

    if isinstance(exc, ConnectorApiError):
        return exc.status_code is None or int(exc.status_code) >= 500

    return False


def calculate_retry_delay(
    *,
    attempt: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float = 0.2,
    random_value: float | None = None,
) -> timedelta:
    base_delay = max(1.0, float(base_delay_seconds))
    max_delay = max(base_delay, float(max_delay_seconds))
    # Exponential Backoff
    exp_delay = min(max_delay, base_delay * (2 ** max(0, attempt - 1)))

    # Jitter 추가
    jitter_ceiling = min(max_delay - exp_delay, exp_delay * max(0.0, jitter_ratio))
    if jitter_ceiling <= 0:
        return timedelta(seconds=exp_delay)

    jitter_unit = random.random() if random_value is None else float(random_value)
    jitter_unit = min(1.0, max(0.0, jitter_unit))
    return timedelta(seconds=exp_delay + (jitter_ceiling * jitter_unit))
