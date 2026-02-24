import logging
import time
import asyncio
from urllib.parse import urlsplit

from redis.asyncio import Redis
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from catchup.configs.config import settings

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None
_checkpointer: AsyncRedisSaver | None = None

OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL = 600  # 10분


async def get_redis_client() -> Redis:
    global _redis_client

    # 이미 생성된 클라이언트가 있으면 재사용한다.
    if _redis_client is not None:
        logger.debug("[REDIS][CLIENT][INIT] Reusing existing Redis client")
        return _redis_client

    # Redis 연결/명령 타임아웃 설정
    socket_connect_timeout = 3.0
    socket_timeout = 5.0
    ping_timeout = 3.0
    health_check_interval = 30

    # 민감정보는 제외하고 연결 대상을 요약해 로그로 남긴다.
    redis_url = urlsplit(settings.REDIS_URL)
    redis_host = redis_url.hostname or "unknown"
    redis_port = redis_url.port or 6379
    redis_db = redis_url.path.lstrip("/") or "0"
    logger.debug(
        (
            "[REDIS][CLIENT][INIT] Creating Redis client: "
            "host=%s, port=%s, db=%s, socket_connect_timeout=%.1fs, "
            "socket_timeout=%.1fs, ping_timeout=%.1fs, health_check_interval=%ss"
        ),
        redis_host,
        redis_port,
        redis_db,
        socket_connect_timeout,
        socket_timeout,
        ping_timeout,
        health_check_interval,
    )

    redis_client: Redis | None = None

    try:
        # 1) 클라이언트 구성
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
            health_check_interval=health_check_interval,
        )

        # 2) 실제 연결 확인 (from_url은 lazy connection이므로 ping으로 검증)
        ping_started_at = time.perf_counter()
        await asyncio.wait_for(redis_client.ping(), timeout=ping_timeout)
        ping_elapsed_ms = (time.perf_counter() - ping_started_at) * 1000

        _redis_client = redis_client
        logger.debug(
            "[REDIS][CLIENT][INIT] Redis client connected successfully: ping_elapsed_ms=%.2f",
            ping_elapsed_ms,
        )
        return _redis_client

    except asyncio.TimeoutError:
        logger.error(
            "[REDIS][CLIENT][INIT] Redis connection timed out: host=%s, port=%s, db=%s",
            redis_host,
            redis_port,
            redis_db,
            exc_info=True,
        )
        if redis_client is not None:
            await redis_client.aclose()
        raise
    except Exception:
        logger.error(
            "[REDIS][CLIENT][INIT] Failed to initialize Redis client: host=%s, port=%s, db=%s",
            redis_host,
            redis_port,
            redis_db,
            exc_info=True,
        )
        if redis_client is not None:
            await redis_client.aclose()
        raise


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


async def init_langgraph_checkpointer() -> None:
    global _checkpointer

    init_started_at = time.perf_counter()
    logger.info("[REDIS][CHECKPOINTER][INIT] Starting LangGraph checkpointer initialization")

    # 이미 초기화된 경우 중복 초기화를 방지한다.
    if _checkpointer is not None:
        logger.debug("[REDIS][CHECKPOINTER][INIT] Skip initialization: checkpointer is already initialized")
        return

    # 민감정보(password)는 로그에 남기지 않고 접속 대상을 요약한다.
    redis_url = urlsplit(settings.REDIS_URL)
    redis_host = redis_url.hostname or "unknown"
    redis_port = redis_url.port or 6379
    redis_db = redis_url.path.lstrip("/") or "0"
    logger.debug(
        "[REDIS][CHECKPOINTER][INIT] Redis target: host=%s, port=%s, db=%s",
        redis_host,
        redis_port,
        redis_db,
    )

    try:
        # Redis client 준비
        redis_client_started_at = time.perf_counter()
        is_reused_client = _redis_client is not None
        redis = await get_redis_client()
        redis_client_elapsed_ms = (time.perf_counter() - redis_client_started_at) * 1000
        logger.debug(
            "[REDIS][CHECKPOINTER][INIT] Redis client ready: reused=%s, elapsed_ms=%.2f",
            is_reused_client,
            redis_client_elapsed_ms,
        )

        # LangGraph 체크포인터 생성 및 내부 인덱스 setup 실행
        saver_started_at = time.perf_counter()
        _checkpointer = AsyncRedisSaver(redis_client=redis)
        logger.debug("[REDIS][CHECKPOINTER][INIT] AsyncRedisSaver instance created")

        setup_started_at = time.perf_counter()
        await _checkpointer.setup()  # 인덱스 생성 (초기 1회)
        setup_elapsed_ms = (time.perf_counter() - setup_started_at) * 1000
        saver_elapsed_ms = (time.perf_counter() - saver_started_at) * 1000
        logger.debug(
            "[REDIS][CHECKPOINTER][INIT] Checkpointer setup completed: setup_elapsed_ms=%.2f, saver_elapsed_ms=%.2f",
            setup_elapsed_ms,
            saver_elapsed_ms,
        )

        total_elapsed_ms = (time.perf_counter() - init_started_at) * 1000
        logger.info(
            "[REDIS][CHECKPOINTER][INIT] Completed initialization: elapsed_ms=%.2f",
            total_elapsed_ms,
        )
    except Exception:
        logger.error(
            "[REDIS][CHECKPOINTER][INIT] Failed to initialize LangGraph checkpointer",
            exc_info=True,
        )
        raise


# RAG 단기 영속성
def get_langgraph_checkpointer() -> AsyncRedisSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph checkpointer is not initialized")
    return _checkpointer
