from __future__ import annotations

from typing import Any

from redis.asyncio.lock import Lock
from redis.exceptions import LockError

from catchup.configs.config import settings
from catchup.connectors.slack.sync_runtime.constants import (
    build_channel_lock_key,
    build_team_active_channels_key,
    build_team_lock_key,
)
from catchup.utils.redis import get_redis_client

def _decode(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)

def _to_token(job_id: str) -> bytes:
    return job_id.encode("utf-8")

def _build_lock(*, redis_client:Any, key: str, timeout_seconds: int) -> Lock:
    return redis_client.lock(
        name = key,
        timeout = timeout_seconds,
        blocking = False,
        thread_local = False,
    )

async def get_team_lock_owner(team_id: str) -> str | None:
    redis = await get_redis_client()
    owner = await redis.get(build_team_lock_key(team_id))
    return _decode(owner)

async def is_team_lock_owner(team_id: str, job_id: str) -> bool:
    owner = await get_team_lock_owner(team_id)
    return owner == job_id

async def acquire_team_lock(team_id: str, job_id: str) -> tuple[bool, str | None]:
    """
    Team 단위 Full Sync Lock 획득
    """
    redis = await get_redis_client()
    key = build_team_lock_key(team_id)

    lock = _build_lock(
        redis_client=redis,
        key=key,
        timeout_seconds=settings.SYNC_LOCK_TEAM_TTL_SECONDS,
    )
    acquired = await lock.acquire(blocking=False, token=_to_token(job_id))
    if acquired:
        return True, None
    
    owner = await redis.get(key)
    return False, _decode(owner)

async def refresh_team_lock_if_owner(team_id: str, job_id: str) -> bool:
    owner = await get_team_lock_owner(team_id)
    if owner!=job_id:
        return False
    
    redis = await get_redis_client()
    key = build_team_lock_key(team_id)
    lock = _build_lock(
        redis_client=redis,
        key=key,
        timeout_seconds=settings.SYNC_LOCK_TEAM_TTL_SECONDS,
    )
    lock.local.token = _to_token(job_id)

    try:
        return await lock.extend(
            additional_time=settings.SYNC_LOCK_TEAM_TTL_SECONDS,
            replace_ttl=True,
        )
    except LockError:
        return False

async def release_team_lock_if_owner(team_id: str, job_id: str) -> bool:

    owner = await get_team_lock_owner(team_id)
    if owner != job_id:
        return False
    
    redis = await get_redis_client()
    key = build_team_lock_key(team_id)
    lock = _build_lock(
        redis_client=redis,
        key=key,
        timeout_seconds=settings.SYNC_LOCK_TEAM_TTL_SECONDS,
    )
    lock.local.token = _to_token(job_id)

    try:
        await lock.release()
        return True
    except LockError:
        return False
    
async def get_channel_lock_owner(team_id: str, channel_id: str) -> str | None:
    redis = await get_redis_client()
    owner = await redis.get(build_channel_lock_key(team_id, channel_id))
    return _decode(owner)

async def acquire_channel_lock(team_id: str, channel_id: str, job_id: str) -> bool:
    redis = await get_redis_client()
    lock_key = build_channel_lock_key(team_id, channel_id)

    lock = _build_lock(
        redis_client=redis,
        key = lock_key,
        timeout_seconds=settings.SYNC_LOCK_CHANNEL_TTL_SECONDS,
    )
    acquired = await lock.acquire(blocking=False, token=_to_token(job_id))
    if not acquired:
        return False
    
    active_set_key = build_team_active_channels_key(team_id)
    await redis.sadd(active_set_key, channel_id)
    await redis.expire(active_set_key, settings.SYNC_LOCK_TEAM_TTL_SECONDS)
    return True

async def refresh_channel_lock_if_owner(team_id: str, channel_id: str, job_id: str) -> bool:
    owner = await get_channel_lock_owner(team_id, channel_id)
    if owner != job_id:
        return False

    redis = await get_redis_client()
    lock_key = build_channel_lock_key(team_id, channel_id)
    lock = _build_lock(
        redis_client=redis,
        key=lock_key,
        timeout_seconds=settings.SYNC_LOCK_CHANNEL_TTL_SECONDS,
    )
    lock.local.token = _to_token(job_id)

    try:
        return await lock.extend(
            additional_time=settings.SYNC_LOCK_CHANNEL_TTL_SECONDS,
            replace_ttl=True,
        )
    except LockError:
        return False    
    
async def release_channel_lock_if_owner(team_id: str, channel_id: str, job_id: str) -> bool:
    owner = await get_channel_lock_owner(team_id, channel_id)
    if owner != job_id:
        return False

    redis = await get_redis_client()
    lock_key = build_channel_lock_key(team_id, channel_id)
    lock = _build_lock(
        redis_client=redis,
        key=lock_key,
        timeout_seconds=settings.SYNC_LOCK_CHANNEL_TTL_SECONDS,
    )
    lock.local.token = _to_token(job_id)

    try:
        await lock.release()
        active_set_key = build_team_active_channels_key(team_id)
        await redis.srem(active_set_key, channel_id)
        return True
    except LockError:
        return False

async def list_active_channels(team_id: str) -> list[str]:
    """
    현재 team에서 lock이 잡힌 channel 목록 조회
    """
    redis = await get_redis_client()
    active_set_key = build_team_active_channels_key(team_id)
    members = await redis.smembers(active_set_key)

    channels: list[str] = []
    for member in members:
        decoded = _decode(member)
        if decoded:
            channels.append(decoded)
    return channels

async def release_all_channel_locks_for_job(team_id: str, job_id: str) -> None:
    """
    job 종료 시 남아있는 channel lock 정리.
    - active set 기준으로 순회
    - owner 검증 후에만 삭제
    """
    channels = await list_active_channels(team_id)
    for channel_id in channels:
        await release_channel_lock_if_owner(team_id, channel_id, job_id)
