from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog

from catchup.chat.schemas import StreamEvent
from catchup.utils.redis import get_stream_redis_client

logger = structlog.get_logger()

CHAT_STREAM_KEY_PREFIX = "chat:events:"
CHAT_STREAM_TTL = 3600
_DONE_SENTINEL = {"type": "DONE"}
_XREAD_BLOCK_MS = 30_000
_XREAD_COUNT = 50
_XREAD_MAX_RETRIES = 120  # 120 × 30s = 1시간


class ChatEventStore:
    """Redis Streams를 사용해 채팅 이벤트를 발행/구독한다."""

    def _key(self, session_id: str) -> str:
        return f"{CHAT_STREAM_KEY_PREFIX}{session_id}"

    async def publish(self, session_id: str, event: StreamEvent) -> None:
        """이벤트를 Redis Stream에 추가하고 TTL을 갱신한다."""
        redis = await get_stream_redis_client()
        key = self._key(session_id)
        await redis.xadd(key, {"data": event.model_dump_json(ensure_ascii=False)})
        await redis.expire(key, CHAT_STREAM_TTL)

    async def publish_done(self, session_id: str) -> None:
        """스트림 종료 센티넬을 발행한다."""
        redis = await get_stream_redis_client()
        key = self._key(session_id)
        await redis.xadd(key, _DONE_SENTINEL)
        await redis.expire(key, CHAT_STREAM_TTL)

    async def subscribe(self, session_id: str) -> AsyncGenerator[str, None]:
        """Redis Stream에서 이벤트를 읽어 raw JSON 문자열로 yield한다.

        DONE 센티넬 수신 시 종료한다. 30초 동안 메시지가 없으면 재시도한다.
        """
        redis = await get_stream_redis_client()
        key = self._key(session_id)
        last_id = "0"
        retries = 0

        while True:
            results = await redis.xread(
                {key: last_id}, count=_XREAD_COUNT, block=_XREAD_BLOCK_MS
            )
            if not results:
                retries += 1
                if retries >= _XREAD_MAX_RETRIES:
                    logger.warning(
                        "subscribe_timeout",
                        session_id=session_id,
                        retries=retries,
                    )
                    return
                continue
            retries = 0  # reset on successful read

            for _stream_key, messages in results:
                for msg_id, fields in messages:
                    last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

                    msg_type = fields.get(b"type") or fields.get("type")
                    if msg_type in (b"DONE", "DONE"):
                        return

                    raw = fields.get(b"data") or fields.get("data")
                    if raw:
                        yield raw.decode() if isinstance(raw, bytes) else raw


_event_store = ChatEventStore()


def get_event_store() -> ChatEventStore:
    """모듈 레벨 싱글턴을 반환한다."""
    return _event_store
