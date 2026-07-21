import uuid
from unittest.mock import AsyncMock

import pytest

from catchup.chat.stream_processor import ChatStreamProcessor


@pytest.mark.asyncio
async def test_emit_token_accumulates_content():
    processor = ChatStreamProcessor(
        session_id=uuid.uuid4(),
        room_id=1,
        save_message=AsyncMock(),
    )
    async for _ in processor._emit_token("hello"):
        pass
    async for _ in processor._emit_token(" world"):
        pass

    assert processor.context.accumulated_content == "hello world"


@pytest.mark.asyncio
async def test_accumulated_content_starts_empty():
    processor = ChatStreamProcessor(
        session_id=uuid.uuid4(),
        room_id=1,
        save_message=AsyncMock(),
    )
    assert processor.context.accumulated_content == ""
    assert processor.context.accumulated_sources == []
