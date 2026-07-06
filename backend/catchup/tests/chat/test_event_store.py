import uuid
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from catchup.chat.event_store import CHAT_STREAM_KEY_PREFIX
from catchup.chat.event_store import CHAT_STREAM_TTL
from catchup.chat.event_store import ChatEventStore
from catchup.chat.schemas import ChatStreamingTokenResponse


@pytest.mark.asyncio
async def test_publish_calls_xadd_and_expire():
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value=b"1-0")
    mock_redis.expire = AsyncMock()

    with patch(
        "catchup.chat.event_store.get_stream_redis_client",
        new=AsyncMock(return_value=mock_redis),
    ):
        store = ChatEventStore()
        session_id = "test-session-123"
        event = ChatStreamingTokenResponse(session_id=uuid.uuid4(), token="hi")

        await store.publish(session_id, event)

        expected_key = f"{CHAT_STREAM_KEY_PREFIX}{session_id}"
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == expected_key
        assert "data" in call_args[0][1]
        mock_redis.expire.assert_called_once_with(expected_key, CHAT_STREAM_TTL)


@pytest.mark.asyncio
async def test_publish_done_sends_done_sentinel():
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value=b"2-0")
    mock_redis.expire = AsyncMock()

    with patch(
        "catchup.chat.event_store.get_stream_redis_client",
        new=AsyncMock(return_value=mock_redis),
    ):
        store = ChatEventStore()
        await store.publish_done("session-abc")

        call_args = mock_redis.xadd.call_args
        assert call_args[0][1] == {"type": "DONE"}


@pytest.mark.asyncio
async def test_clear_deletes_session_stream_key():
    """clear()는 세션의 스트림 키를 삭제해 다음 턴이 이전 턴의 잔존 이벤트/DONE 센티넬을
    리플레이하지 않고 깨끗하게 시작하도록 해야 한다."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()

    with patch(
        "catchup.chat.event_store.get_stream_redis_client",
        new=AsyncMock(return_value=mock_redis),
    ):
        store = ChatEventStore()
        await store.clear("session-to-clear")

        expected_key = f"{CHAT_STREAM_KEY_PREFIX}session-to-clear"
        mock_redis.delete.assert_called_once_with(expected_key)


@pytest.mark.asyncio
async def test_subscribe_yields_events_and_stops_on_done():
    session_id = "sub-session"
    key = f"{CHAT_STREAM_KEY_PREFIX}{session_id}".encode()

    mock_redis = AsyncMock()
    # 첫 번째 xread: 데이터 이벤트 + DONE
    mock_redis.xread = AsyncMock(
        return_value=[
            [
                key,
                [
                    (b"1-0", {b"data": b'{"type":"token","session_id":"00000000-0000-0000-0000-000000000000","token":"hello"}'}),
                    (b"2-0", {b"type": b"DONE"}),
                ],
            ]
        ]
    )

    with patch(
        "catchup.chat.event_store.get_chat_stream_redis_client",
        new=AsyncMock(return_value=mock_redis),
    ):
        store = ChatEventStore()
        results = []
        async for event_id, raw in store.subscribe(session_id):
            results.append((event_id, raw))

    assert len(results) == 1
    assert results[0][0] == "1-0"
    assert '"token"' in results[0][1]
