import logging
import time
import asyncio
from urllib.parse import urlsplit

from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster

from catchup.configs.config import settings
from catchup.configs.constants import (
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    REDIS_PING_TIMEOUT_SECONDS,
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
    REDIS_SOCKET_TIMEOUT_SECONDS,
    REDIS_STREAM_SOCKET_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

_redis_client: RedisCluster | Redis | None = None
_stream_redis_client: RedisCluster | Redis | None = None

OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL = 600  # 10분


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


async def get_redis_client() -> RedisCluster | Redis:
    global _redis_client

    # 이미 생성된 클라이언트가 있으면 재사용한다.
    if _redis_client is not None:
        return _redis_client

    _redis_client = await _create_redis_client(
        client_type="default",
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
    )
    return _redis_client


async def get_stream_redis_client() -> RedisCluster | Redis:
    global _stream_redis_client

    if _stream_redis_client is not None:
        return _stream_redis_client

    _stream_redis_client = await _create_redis_client(
        client_type="stream",
        socket_timeout=REDIS_STREAM_SOCKET_TIMEOUT_SECONDS,
    )
    return _stream_redis_client


async def store_oauth_state(state: str, provider: str) -> None:
    """OAuth state를 Redis에 저장 (TTL: 10분)"""
    redis = await get_redis_client()
    key = f"{OAUTH_STATE_PREFIX}{provider}:{state}"
    await redis.setex(key, OAUTH_STATE_TTL, "1")


async def validate_oauth_state(state: str, provider: str) -> bool:
    """OAuth state 검증 후 삭제 (일회성 사용)"""
    redis = await get_redis_client()
    key = f"{OAUTH_STATE_PREFIX}{provider}:{state}"
    result = await redis.delete(key)
    return result > 0


async def check_redis_health() -> bool:
    """Redis 서버 상태를 확인합니다."""
    try:
        # get_redis_client() 내부에서 이미 ping을 수행하므로 호출만으로 검증 가능합니다.
        client = await get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        logger.error(f"[REDIS][HEALTH] Health check failed: {e}")
        return False
