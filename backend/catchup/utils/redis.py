from redis.asyncio import Redis

from catchup.configs.config import settings


_redis_client: Redis | None = None

OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL = 600  # 10분


async def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL)
    return _redis_client


async def store_oauth_state(state: str, provider: str = "slack") -> None:
    """OAuth state를 Redis에 저장 (TTL: 10분)"""
    redis = await get_redis_client()
    key = f"{OAUTH_STATE_PREFIX}{provider}:{state}"
    await redis.setex(key, OAUTH_STATE_TTL, "1")


async def validate_oauth_state(state: str, provider: str = "slack") -> bool:
    """OAuth state 검증 후 삭제 (일회성 사용)"""
    redis = await get_redis_client()
    key = f"{OAUTH_STATE_PREFIX}{provider}:{state}"
    result = await redis.delete(key)
    return result > 0
