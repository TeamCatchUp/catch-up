from redis.asyncio import Redis
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from catchup.configs.config import settings


_redis_client: Redis | None = None
_checkpointer: AsyncRedisSaver | None = None

OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL = 600  # 10분


async def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL)
    return _redis_client


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

    if _checkpointer is not None:
        return

    redis = await get_redis_client()
    _checkpointer = AsyncRedisSaver(redis_client=redis)
    await _checkpointer.setup()  # 인덱스 생성 (초기 1회)


# RAG 단기 영속성
def get_langgraph_checkpointer() -> AsyncRedisSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph checkpointer is not initialized")
    return _checkpointer