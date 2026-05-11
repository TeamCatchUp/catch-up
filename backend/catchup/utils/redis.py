import asyncio
import json
import logging
import time
from typing import Any
from urllib.parse import urlsplit

from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster

from catchup.configs.config import settings
from catchup.configs.constants import REDIS_HEALTH_CHECK_INTERVAL_SECONDS
from catchup.configs.constants import REDIS_PING_TIMEOUT_SECONDS
from catchup.configs.constants import REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS
from catchup.configs.constants import REDIS_SOCKET_TIMEOUT_SECONDS
from catchup.configs.constants import REDIS_STREAM_SOCKET_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_redis_client: RedisCluster | Redis | None = None
_stream_redis_client: RedisCluster | Redis | None = None
_redis_client_lock = asyncio.Lock()
_stream_redis_client_lock = asyncio.Lock()

OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL = 600  # 10분
OAUTH_STATE_PURPOSES = {"sync_install", "workflow_personal"}


async def _create_redis_client(
    *,
    client_type: str,
    socket_timeout: float,
) -> RedisCluster | Redis:
    # Redis 연결/명령 타임아웃 설정
    socket_connect_timeout = REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS
    ping_timeout = REDIS_PING_TIMEOUT_SECONDS
    health_check_interval = REDIS_HEALTH_CHECK_INTERVAL_SECONDS

    # 민감정보는 제외하고 연결 대상을 요약해 로그로 남김
    redis_url = urlsplit(settings.REDIS_URL)
    redis_host = redis_url.hostname or "unknown"
    redis_port = redis_url.port or 6379
    redis_db = redis_url.path.lstrip("/") or "0"
    
    is_cluster_mode = settings.REDIS_CLUSTER_MODE

    logger.debug(
        (
            "[REDIS][CLIENT][INIT] Creating Redis client: "
            "client_type=%s, host=%s, port=%s, db=%s, cluster_mode=%s, socket_connect_timeout=%.1fs, "
            "socket_timeout=%.1fs, ping_timeout=%.1fs, health_check_interval=%ss"
        ),
        client_type,
        redis_host,
        redis_port,
        redis_db,
        is_cluster_mode,
        socket_connect_timeout,
        socket_timeout,
        ping_timeout,
        health_check_interval,
    )

    redis_client: RedisCluster | Redis | None = None

    try:
        # 클라이언트 구성
        if is_cluster_mode:
            # rediss:// (SSL) 환경 대응
            ssl_opts = {}
            if redis_url.scheme == "rediss":
                ssl_opts = {"ssl": True, "ssl_cert_reqs": None}
                
            redis_client = RedisCluster.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=socket_connect_timeout,
                socket_timeout=socket_timeout,
                health_check_interval=health_check_interval,
                require_full_coverage=False,
                **ssl_opts
            )
        else:
            redis_client = Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=socket_connect_timeout,
                socket_timeout=socket_timeout,
                health_check_interval=health_check_interval,
            )

        # 실제 연결 확인 (from_url은 lazy connection이므로 ping으로 검증)
        ping_started_at = time.perf_counter()
        await asyncio.wait_for(redis_client.ping(), timeout=ping_timeout)
        ping_elapsed_ms = (time.perf_counter() - ping_started_at) * 1000

        logger.debug(
            "[REDIS][CLIENT][INIT] Redis client connected successfully: client_type=%s, ping_elapsed_ms=%.2f",
            client_type,
            ping_elapsed_ms,
        )
        return redis_client

    except asyncio.TimeoutError:
        logger.error(
            "[REDIS][CLIENT][INIT] Redis connection timed out: client_type=%s, host=%s, port=%s, db=%s, cluster_mode=%s",
            client_type,
            redis_host,
            redis_port,
            redis_db,
            is_cluster_mode,
            exc_info=True,
        )
        if redis_client is not None:
            await redis_client.aclose()
        raise
    except Exception:
        logger.error(
            "[REDIS][CLIENT][INIT] Failed to initialize Redis client: client_type=%s, host=%s, port=%s, db=%s, cluster_mode=%s",
            client_type,
            redis_host,
            redis_port,
            redis_db,
            is_cluster_mode,
            exc_info=True,
        )
        if redis_client is not None:
            await redis_client.aclose()
        raise


async def _create_stream_redis_client(
    *,
    client_type: str,
    socket_timeout: float,
) -> Redis:
    socket_connect_timeout = REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS
    ping_timeout = REDIS_PING_TIMEOUT_SECONDS
    health_check_interval = REDIS_HEALTH_CHECK_INTERVAL_SECONDS

    redis_url = urlsplit(settings.REDIS_URL)
    redis_host = redis_url.hostname or "unknown"
    redis_port = redis_url.port or 6379
    redis_db = redis_url.path.lstrip("/") or "0"

    logger.debug(
        (
            "[REDIS][CLIENT][INIT] Creating Redis client: "
            "client_type=%s, host=%s, port=%s, db=%s, cluster_mode=%s, socket_connect_timeout=%.1fs, "
            "socket_timeout=%.1fs, ping_timeout=%.1fs, health_check_interval=%ss"
        ),
        client_type,
        redis_host,
        redis_port,
        redis_db,
        False,
        socket_connect_timeout,
        socket_timeout,
        ping_timeout,
        health_check_interval,
    )

    redis_client: Redis | None = None

    try:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
            health_check_interval=health_check_interval,
        )

        ping_started_at = time.perf_counter()
        await asyncio.wait_for(redis_client.ping(), timeout=ping_timeout)
        ping_elapsed_ms = (time.perf_counter() - ping_started_at) * 1000

        logger.debug(
            "[REDIS][CLIENT][INIT] Redis client connected successfully: client_type=%s, ping_elapsed_ms=%.2f",
            client_type,
            ping_elapsed_ms,
        )
        return redis_client

    except asyncio.TimeoutError:
        logger.error(
            "[REDIS][CLIENT][INIT] Redis connection timed out: client_type=%s, host=%s, port=%s, db=%s, cluster_mode=%s",
            client_type,
            redis_host,
            redis_port,
            redis_db,
            False,
            exc_info=True,
        )
        if redis_client is not None:
            await redis_client.aclose()
        raise
    except Exception:
        logger.error(
            "[REDIS][CLIENT][INIT] Failed to initialize Redis client: client_type=%s, host=%s, port=%s, db=%s, cluster_mode=%s",
            client_type,
            redis_host,
            redis_port,
            redis_db,
            False,
            exc_info=True,
        )
        if redis_client is not None:
            await redis_client.aclose()
        raise


async def get_redis_client() -> RedisCluster | Redis:
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    async with _redis_client_lock:
        if _redis_client is not None:
            return _redis_client

        _redis_client = await _create_redis_client(
            client_type="default",
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        )
    return _redis_client


async def get_stream_redis_client() -> Redis:
    global _stream_redis_client

    if _stream_redis_client is not None:
        return _stream_redis_client

    async with _stream_redis_client_lock:
        if _stream_redis_client is not None:
            return _stream_redis_client

        _stream_redis_client = await _create_stream_redis_client(
            client_type="stream",
            socket_timeout=REDIS_STREAM_SOCKET_TIMEOUT_SECONDS,
        )
    return _stream_redis_client


async def reset_stream_redis_client(
    client: RedisCluster | Redis | None = None,
) -> None:
    global _stream_redis_client

    async with _stream_redis_client_lock:
        current_client = _stream_redis_client
        if current_client is None:
            return
        if client is not None and current_client is not client:
            return

        _stream_redis_client = None

    try:
        await current_client.aclose()
    except Exception:
        logger.warning(
            "[REDIS][CLIENT][RESET] Failed to close stream Redis client",
            exc_info=True,
        )
    else:
        logger.warning("[REDIS][CLIENT][RESET] Stream Redis client reset")


async def check_all_redis_health() -> bool:
    """공용/stream Redis 클라이언트 상태를 모두 확인합니다."""
    try:
        default_client, stream_client = await asyncio.gather(
            get_redis_client(),
            get_stream_redis_client(),
        )
        await asyncio.gather(
            default_client.ping(),
            stream_client.ping(),
        )
        return True
    except Exception as e:
        logger.error(f"[REDIS][HEALTH] Health check failed: {e}")
        return False


async def store_oauth_state(state: str, provider: str) -> None:
    """OAuth state를 Redis에 저장 (TTL: 10분)"""
    await store_oauth_state_payload(
        provider=provider,
        state=state,
        payload={
            "purpose": "sync_install",
            "vendor": provider,
        },
    )


async def store_oauth_state_payload(
    *,
    provider: str,
    state: str,
    payload: dict[str, Any],
) -> None:
    """Payload-aware OAuth state를 Redis에 저장 (TTL: 10분)."""
    if payload.get("vendor") != provider:
        raise ValueError("OAuth state payload vendor must match provider")

    if payload.get("purpose") not in OAUTH_STATE_PURPOSES:
        raise ValueError("Unsupported OAuth state purpose")

    redis = await get_redis_client()
    key = f"{OAUTH_STATE_PREFIX}{provider}:{state}"
    await redis.setex(key, OAUTH_STATE_TTL, json.dumps(payload))


async def consume_oauth_state_payload(
    *,
    provider: str,
    state: str,
) -> dict[str, Any] | None:
    """OAuth state payload를 검증 후 삭제한다.

    Legacy Redis 값 `"1"`은 in-flight compatibility를 위해 `sync_install`로만
    해석한다. 그 외 malformed payload는 명시적으로 거부한다.
    """
    redis = await get_redis_client()
    key = f"{OAUTH_STATE_PREFIX}{provider}:{state}"
    raw_value = await redis.getdel(key)
    if raw_value is None:
        return None

    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")

    if raw_value == "1":
        return {
            "purpose": "sync_install",
            "vendor": provider,
            "legacy": True,
        }

    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("vendor") != provider:
        return None

    if payload.get("purpose") not in OAUTH_STATE_PURPOSES:
        return None

    return payload


async def validate_oauth_state(state: str, provider: str) -> bool:
    """OAuth state 검증 후 삭제 (일회성 사용)"""
    payload = await consume_oauth_state_payload(provider=provider, state=state)
    return payload is not None


async def check_redis_health() -> bool:
    """Redis 서버 상태를 확인합니다."""
    return await check_all_redis_health()
