from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from catchup.chat.integrations import slack_app_mention as app_mention_module

SlackAppMentionOrchestrator = app_mention_module.SlackAppMentionOrchestrator
SlackAppMentionRequest = app_mention_module.SlackAppMentionRequest


class FakeTransport:
    def __init__(self, responder: object | None = None) -> None:
        self.responder = responder or FakeResponder()
        self.post_thread_reply = AsyncMock()
        self.post_signup_prompt = AsyncMock()
        self.post_busy_notice = AsyncMock()
        self.start_responder = AsyncMock(return_value=self.responder)


class FakeResponder:
    def __init__(self) -> None:
        self.finish = AsyncMock()
        self.fail = AsyncMock()
        self.on_process = AsyncMock()
        self.on_sources = AsyncMock()
        self.append_answer_markdown = AsyncMock()


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _mention(query: str, *, raw_text: str | None = None) -> SlackAppMentionRequest:
    return SlackAppMentionRequest(
        team_id="T123",
        channel_id="C123",
        thread_ts="1712741200.000100",
        event_ts="1712741200.000100",
        slack_user_id="U123",
        raw_text=raw_text or f"<@UBOT> {query}",
        query=query,
    )


class SlackAppMentionOrchestratorTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.run_in_threadpool_patcher = patch.object(
            app_mention_module,
            "run_in_threadpool",
            _run_immediately,
        )
        self.run_in_threadpool_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)
        self.orchestrator = SlackAppMentionOrchestrator()

    async def test_posts_empty_query_message(self) -> None:
        transport = FakeTransport()

        await self.orchestrator.handle_mention(
            _mention("", raw_text="<@UBOT>"),
            bot_user_id="UBOT",
            transport=transport,
        )

        transport.post_thread_reply.assert_awaited_once()
        self.assertEqual(
            transport.post_thread_reply.await_args.args[1],
            app_mention_module.EMPTY_QUERY_MESSAGE,
        )

    async def test_posts_unmapped_user_message(self) -> None:
        transport = FakeTransport()

        with patch.object(
            self.orchestrator,
            "_find_internal_user_id_sync",
            return_value=None,
        ):
            await self.orchestrator.handle_mention(
                _mention("hello"),
                bot_user_id="UBOT",
                transport=transport,
            )

        transport.post_signup_prompt.assert_awaited_once()
        self.assertEqual(
            transport.post_signup_prompt.await_args.args[1],
            app_mention_module.UNMAPPED_USER_MESSAGE,
        )

    async def test_posts_missing_context_message(self) -> None:
        transport = FakeTransport()

        with (
            patch.object(self.orchestrator, "_find_internal_user_id_sync", return_value=7),
            patch.object(self.orchestrator, "_load_global_context_sync", return_value=None),
        ):
            await self.orchestrator.handle_mention(
                _mention("hello"),
                bot_user_id="UBOT",
                transport=transport,
            )

        transport.post_signup_prompt.assert_awaited_once()
        self.assertEqual(
            transport.post_signup_prompt.await_args.args[1],
            app_mention_module.MISSING_CONTEXT_MESSAGE,
        )

    async def test_posts_busy_notice_when_thread_is_already_running(self) -> None:
        transport = FakeTransport()

        with (
            patch.object(self.orchestrator, "_find_internal_user_id_sync", return_value=7),
            patch.object(
                self.orchestrator,
                "_load_global_context_sync",
                return_value=SimpleNamespace(user_id=7),
            ),
            patch.object(
                self.orchestrator,
                "_acquire_thread_session_sync",
                return_value=SimpleNamespace(
                    outcome="busy",
                    session_id=None,
                    lease_started_at=None,
                    reclaimed_stale=False,
                ),
            ),
        ):
            await self.orchestrator.handle_mention(
                _mention("hello"),
                bot_user_id="UBOT",
                transport=transport,
            )

        transport.post_busy_notice.assert_awaited_once()
        transport.start_responder.assert_not_awaited()

    async def test_finishes_responder_and_attaches_chat_room_on_stream_success(self) -> None:
        responder = FakeResponder()
        transport = FakeTransport(responder)
        session_id = uuid.uuid4()
        answer_ref = app_mention_module.SlackChatAnswerRef(session_id=session_id)
        run_chat_stream = AsyncMock(return_value=("final answer", [{"title": "Doc"}]))
        attach_chat_room = Mock()
        release_thread = Mock(return_value=True)

        with (
            patch.object(self.orchestrator, "_find_internal_user_id_sync", return_value=7),
            patch.object(
                self.orchestrator,
                "_load_global_context_sync",
                return_value=SimpleNamespace(user_id=7),
            ),
            patch.object(
                self.orchestrator,
                "_acquire_thread_session_sync",
                return_value=SimpleNamespace(
                    outcome="acquired",
                    session_id=session_id,
                    lease_started_at="lease",
                    reclaimed_stale=False,
                ),
            ),
            patch.object(
                self.orchestrator,
                "_load_prompt_settings_sync",
                return_value=SimpleNamespace(platform="slack"),
            ),
            patch.object(self.orchestrator, "_run_chat_stream", run_chat_stream),
            patch.object(self.orchestrator, "_load_answer_ref_sync", return_value=answer_ref),
            patch.object(self.orchestrator, "_attach_chat_room_if_ready_sync", attach_chat_room),
            patch.object(self.orchestrator, "_release_thread_execution_sync", release_thread),
        ):
            await self.orchestrator.handle_mention(
                _mention("hello"),
                bot_user_id="UBOT",
                transport=transport,
            )

        transport.start_responder.assert_awaited_once()
        run_chat_stream.assert_awaited_once()
        responder.finish.assert_awaited_once_with(
            answer="final answer",
            sources=[{"title": "Doc"}],
            answer_ref=answer_ref,
        )
        responder.fail.assert_not_awaited()
        attach_chat_room.assert_called_once()
        release_thread.assert_called_once()

    async def test_fails_responder_and_reraises_stream_errors(self) -> None:
        responder = FakeResponder()
        transport = FakeTransport(responder)
        session_id = uuid.uuid4()
        run_chat_stream = AsyncMock(side_effect=RuntimeError("boom"))
        attach_chat_room = Mock()
        release_thread = Mock(return_value=True)

        with (
            patch.object(self.orchestrator, "_find_internal_user_id_sync", return_value=7),
            patch.object(
                self.orchestrator,
                "_load_global_context_sync",
                return_value=SimpleNamespace(user_id=7),
            ),
            patch.object(
                self.orchestrator,
                "_acquire_thread_session_sync",
                return_value=SimpleNamespace(
                    outcome="acquired",
                    session_id=session_id,
                    lease_started_at="lease",
                    reclaimed_stale=False,
                ),
            ),
            patch.object(
                self.orchestrator,
                "_load_prompt_settings_sync",
                return_value=SimpleNamespace(platform="slack"),
            ),
            patch.object(self.orchestrator, "_run_chat_stream", run_chat_stream),
            patch.object(self.orchestrator, "_attach_chat_room_if_ready_sync", attach_chat_room),
            patch.object(self.orchestrator, "_release_thread_execution_sync", release_thread),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                await self.orchestrator.handle_mention(
                    _mention("hello"),
                    bot_user_id="UBOT",
                    transport=transport,
                )

        responder.fail.assert_awaited_once_with(app_mention_module.STREAM_FAILED_MESSAGE)
        responder.finish.assert_not_awaited()
        attach_chat_room.assert_not_called()
        release_thread.assert_called_once()
