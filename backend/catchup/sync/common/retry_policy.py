from __future__ import annotations

import asyncio
import math
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
from catchup.sync.common.exceptions import RedisStreamInitializationException
from catchup.sync.common.exceptions import RedisStreamPublishException
from catchup.sync.common.exceptions import SyncInternalException


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
            RedisStreamInitializationException,
            RedisStreamPublishException,
            SyncInternalException,

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


def extract_retry_after_seconds(exc: Exception) -> int | None:
    if not isinstance(exc, ConnectorApiError):
        return None

    retry_after = exc.retry_after
    if retry_after is None:
        return None

    try:
        seconds = math.ceil(float(retry_after))
    except (TypeError, ValueError):
        return None

    return max(1, seconds)


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
    exp_delay = min(max_delay, base_delay * (2 ** max(0, attempt - 1)))

    # Jitter 추가
    jitter_ceiling = min(max_delay - exp_delay, exp_delay * max(0.0, jitter_ratio))
    if jitter_ceiling <= 0:
        return timedelta(seconds=exp_delay)

    jitter_unit = random.random() if random_value is None else float(random_value)
    jitter_unit = min(1.0, max(0.0, jitter_unit))
    return timedelta(seconds=exp_delay + (jitter_ceiling * jitter_unit))


def resolve_retry_delay(
    *,
    exc: Exception,
    attempt: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float = 0.2,
    random_value: float | None = None,
) -> timedelta:
    retry_after_seconds = extract_retry_after_seconds(exc)
    if retry_after_seconds is not None:
        if isinstance(exc, RateLimitError):
            return timedelta(seconds=retry_after_seconds)

        capped_seconds = min(
            retry_after_seconds,
            max(1, int(max_delay_seconds)),
        )
        return timedelta(seconds=capped_seconds)

    return calculate_retry_delay(
        attempt=attempt,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        jitter_ratio=jitter_ratio,
        random_value=random_value,
    )
