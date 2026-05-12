from __future__ import annotations

import uuid
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.chat.integrations.slack_app_mention import SlackAppMentionOrchestrator
from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.chat.schemas import ChatStreamingTokenResponse
from catchup.server.connector.slack.app_mention_adapter import (
    CATCHUP_TURN_CONTEXT_MARKER,
)
from catchup.server.connector.slack.app_mention_adapter import SlackAppMentionAdapter


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


class SlackAppMentionThreadContextTests(IsolatedAsyncioTestCase):
    def test_thread_context_keeps_all_slack_messages_and_masks_catchup_turns(self) -> None:
        adapter = SlackAppMentionAdapter()

        context_messages = adapter._build_context_messages(
            [
                {
                    "ts": "1710000000.000000",
                    "user": "UROOT",
                    "text": "배포 언제?",
                },
                {
                    "ts": "1710000010.000000",
                    "user": "UASKER",
                    "text": "<@UBOT> 배포 언제?",
                },
                {
                    "ts": "1710000020.000000",
                    "user": "UBOT",
                    "bot_id": "B_CATCHUP",
                    "text": "내일 배포 예정입니다.",
                },
                {
                    "ts": "1710000030.000000",
                    "user": "UTEAMMATE",
                    "text": "정확히는 오전 10시예요.",
                },
                {
                    "ts": "1710000035.000000",
                    "user": "UDEPLOYBOT",
                    "bot_id": "B_DEPLOY",
                    "subtype": "bot_message",
                    "text": "배포 파이프라인은 대기 중입니다.",
                },
                {
                    "ts": "1710000040.000000",
                    "user": "UASKER",
                    "text": "<@UBOT> 담당자는 누구야?",
                },
                {
                    "ts": "1710000050.000000",
                    "user": "UBOT",
                    "bot_id": "B_CATCHUP",
                    "text": "플랫폼 팀입니다.",
                },
            ],
            bot_user_id="UBOT",
        )

        additional_context = adapter._format_additional_context(
            context_messages,
            user_names_by_id={
                "UROOT": "원문작성자",
                "UTEAMMATE": "팀원",
                "UDEPLOYBOT": "DeployBot",
            },
        )

        self.assertEqual(
            additional_context,
            "\n".join(
                [
                    "Thread context:",
                    "- [원문작성자 at 2024-03-09 16:00] 배포 언제?",
                    CATCHUP_TURN_CONTEXT_MARKER,
                    "- [팀원 at 2024-03-09 16:00] 정확히는 오전 10시예요.",
                    "- [DeployBot at 2024-03-09 16:00] 배포 파이프라인은 대기 중입니다.",
                    CATCHUP_TURN_CONTEXT_MARKER,
                ]
            ),
        )
