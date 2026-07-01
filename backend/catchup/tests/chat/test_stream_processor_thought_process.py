import uuid
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.chat.stream_processor import ChatStreamProcessor


class ChatStreamProcessorThoughtProcessTests(IsolatedAsyncioTestCase):
    """ChatStreamProcessor의 process 이벤트 변환을 검증한다."""

    async def test_process_process_event(self):
        # Given
        session_id = uuid.uuid4()
        room_id = 1
        save_message = AsyncMock()
        processor = ChatStreamProcessor(session_id, room_id, save_message)

        event = {
            "event": "on_custom_event",
            "name": "process",
            "data": {
                "status": "completed",
                "node": "supervisor",
                "reasoning": "테스트 이유",
                "content": {"query_type": "standard"},
            },
        }

        # When
        responses = []
        async for res in processor.process(event):
            responses.append(res)

        # Then
        self.assertEqual(len(responses), 1)
        res = responses[0]
        self.assertIsInstance(res, ChatStreamingProcessResponse)
        self.assertEqual(res.type, "process")
        self.assertEqual(res.session_id, session_id)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.node, "supervisor")
        self.assertEqual(res.reasoning, "테스트 이유")
        self.assertEqual(res.content, {"query_type": "standard"})
