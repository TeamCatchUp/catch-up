from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catchup.configs.config import settings
from catchup.connectors.slack.sync_runtime.constants import (
    SyncJobStatus,
    build_job_meta_key,
)
from catchup.connectors.slack.sync_runtime.schemas import SyncJobMeta
from catchup.utils.redis import get_redis_client

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_redis_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)

async def create_job(meta: SyncJobMeta) -> None:
    redis = await get_redis_client()
    key = build_job_meta_key(meta.job_id)

    await redis.hset(key, mapping=meta.to_redis_hash())
    await redis.expire(key, settings.SYNC_JOB_META_TTL_SECONDS)

async def get_job(job_id: str) -> SyncJobMeta | None:
    redis = await get_redis_client()
    key = build_job_meta_key(job_id)
    data = await redis.hgetall(key)

    if not data:
        return None
    
    return SyncJobMeta.from_redis_hash(data)

async def exists_job(job_id: str) -> bool:
    redis = await get_redis_client()
    key = build_job_meta_key(job_id)
    return bool(await redis.exists(key))

async def update_job_fields(job_id:str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    
    redis = await get_redis_client()
    key = build_job_meta_key(job_id)

    serialized = {k: _to_redis_value(v) for k,v in fields.items()}
    await redis.hset(key, mapping=serialized)
    await redis.expire(key, settings.SYNC_JOB_META_TTL_SECONDS)

async def increment_field(job_id: str, field:str, amount: int = 1) -> int:
    redis = await get_redis_client()
    key = build_job_meta_key(job_id)

    value = await redis.hincrby(key, field, amount)
    await redis.expire(key, settings.SYNC_JOB_META_TTL_SECONDS)
    return int(value)

async def mark_job_started(job_id: str) -> None:
    await update_job_fields(
        job_id=job_id,
        fields={
            "status": SyncJobStatus.IN_PROGRESS.value,
            "started_at": _now_iso(),
        },
    )


async def mark_job_started_if_accepted(job_id: str) -> bool:
    redis = await get_redis_client()
    key = build_job_meta_key(job_id)

    status = await redis.hget(key, "status")
    if status is None or _decode(status) != SyncJobStatus.ACCEPTED.value:
        return False

    gate_field = "_job_started_once"
    gate_set = await redis.hsetnx(key, gate_field, "1")
    if int(gate_set) != 1:
        return False

    try:
        await redis.hset(
            key,
            mapping={
                "status": SyncJobStatus.IN_PROGRESS.value,
                "started_at": _now_iso(),
            },
        )
        await redis.expire(key, settings.SYNC_JOB_META_TTL_SECONDS)
        return True
    except Exception:
        await redis.hdel(key, gate_field)
        raise

async def mark_job_completed(
    job_id: str,
    *,
    failed_channels: int = 0,
    last_error: str | None = None,
) -> None:
    final_status = (
        SyncJobStatus.FAILED.value
        if failed_channels > 0
        else SyncJobStatus.SUCCESS.value
    )

    await update_job_fields(
        job_id=job_id,
        fields={
            "status": final_status,
            "completed_at": _now_iso(),
            "last_error": last_error,
        },
    )


async def set_last_error(job_id: str, error_message: str | None) -> None:
    await update_job_fields(
        job_id=job_id,
        fields={"last_error": error_message},
    )
