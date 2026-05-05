from __future__ import annotations

import uuid
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.chat.integrations.slack_app_mention import SlackAppMentionOrchestrator
from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.chat.schemas import ChatStreamingTokenResponse


class _FakeChatService:
    async def chat_stream(self, **kwargs):
        del kwargs
        yield ChatStreamingProcessResponse(
            session_id=uuid.uuid4(),
            status="completed",
            node="supervisor",
            reasoning="문서를 찾아볼게요.",
        )
        yield ChatStreamingProcessResponse(
            session_id=uuid.uuid4(),
            status="in_progress",
            node="generate_final_answer",
        )
        yield ChatStreamingTokenResponse(
            session_id=uuid.uuid4(),
            token="답변",
        )


class _FakeResponder:
    def __init__(self) -> None:
        self.on_process = AsyncMock()
        self.append_answer_markdown = AsyncMock()
        self.on_sources = AsyncMock()


class SlackAppMentionProcessTests(IsolatedAsyncioTestCase):
    async def test_run_chat_stream_forwards_full_process_to_responder(self) -> None:
        responder = _FakeResponder()
        orchestrator = SlackAppMentionOrchestrator()

        with patch(
            "catchup.chat.integrations.slack_app_mention.get_chat_service",
            return_value=_FakeChatService(),
        ):
            answer, sources = await orchestrator._run_chat_stream(
                global_context=object(),
                prompt_settings=object(),
                session_id=uuid.uuid4(),
                query="질문",
                additional_context=None,
                responder=responder,
            )

        self.assertEqual(answer, "답변")
        self.assertEqual(sources, [])
        self.assertEqual(responder.on_process.await_count, 2)
        first_process = responder.on_process.await_args_list[0].args[0]
        self.assertEqual(first_process.reasoning, "문서를 찾아볼게요.")
        responder.append_answer_markdown.assert_awaited_once_with("답변")

