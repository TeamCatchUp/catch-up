from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog

from catchup.chat.schemas import StreamEvent
from catchup.utils.redis import get_chat_stream_redis_client
from catchup.utils.redis import get_stream_redis_client

logger = structlog.get_logger()

CHAT_STREAM_KEY_PREFIX = "chat:events:"
CHAT_STREAM_TTL = 3600
_DONE_SENTINEL = {"type": "DONE"}
_XREAD_BLOCK_MS = 30_000
_XREAD_COUNT = 50
_XREAD_MAX_RETRIES = 120  # 120 × 30s = 1시간
# XREAD BLOCK 대기 중에는 서버가 최대 _XREAD_BLOCK_MS까지 정상적으로 블로킹
# 하므로, 클라이언트 소켓 타임아웃이 이보다 짧으면 서버가 응답하기 전에
# 클라이언트가 먼저 TimeoutError를 던진다. 여유 마진을 더해 소켓 타임아웃을
# 계산한다.
_XREAD_SOCKET_TIMEOUT_MARGIN_SECONDS = 10.0
_XREAD_SOCKET_TIMEOUT_SECONDS = (
    _XREAD_BLOCK_MS / 1000 + _XREAD_SOCKET_TIMEOUT_MARGIN_SECONDS
)


class ChatEventStore:
    """Redis Streams를 사용해 채팅 이벤트를 발행/구독한다."""

    def _key(self, session_id: str) -> str:
        return f"{CHAT_STREAM_KEY_PREFIX}{session_id}"

    async def clear(self, session_id: str) -> None:
        """세션의 스트림 키를 삭제한다.

        스트림 키가 session_id에만 묶여 있어 턴마다 누적되므로, 지우지 않으면
        다음 턴의 subscribe()가 이전 턴의 이벤트와 DONE 센티넬을 리플레이하다
        그 DONE에서 즉시 종료돼 새 턴의 실시간 이벤트를 받지 못한다.
        """
        redis = await get_stream_redis_client()
        await redis.delete(self._key(session_id))

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

    async def subscribe(
        self, session_id: str
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Redis Stream에서 이벤트를 읽어 (이벤트 ID, raw JSON 문자열) 튜플로 yield한다.

        DONE 센티넬 수신 시 종료한다. 30초 동안 메시지가 없으면 재시도한다.
        """
        redis = await get_chat_stream_redis_client(
            socket_timeout=_XREAD_SOCKET_TIMEOUT_SECONDS
        )
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
                        yield last_id, raw.decode() if isinstance(raw, bytes) else raw

    async def get_tail_id(self, session_id: str) -> tuple[str | None, bool]:
        """스트림의 마지막 엔트리를 non-blocking으로 조회해 배치/실시간 렌더링 경계를 계산한다.

        반환: (마지막 실이벤트 ID 또는 None, DONE 센티넬로 끝났는지 여부).
        스트림이 비어 있으면 (None, False)를 반환한다.
        """
        redis = await get_stream_redis_client()
        key = self._key(session_id)
        entries = await redis.xrevrange(key, max="+", min="-", count=1)

        if not entries:
            return None, False

        msg_id, fields = entries[0]
        entry_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

        msg_type = fields.get(b"type") or fields.get("type")
        if msg_type in (b"DONE", "DONE"):
            return None, True

        return entry_id, False


_event_store = ChatEventStore()


def get_event_store() -> ChatEventStore:
    """모듈 레벨 싱글턴을 반환한다."""
    return _event_store
