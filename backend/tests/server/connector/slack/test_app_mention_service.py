from __future__ import annotations

import importlib
import uuid
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch


def _import_first(*module_names: str):
    last_error: Exception | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("no module names provided")


schemas = _import_first(
    "catchup.server.connector.slack.schemas",
    "catchup.sync.ingress.types",
)
app_mention_module = _import_first(
    "catchup.chat.integrations.slack_app_mention",
    "catchup.server.connector.slack.app_mention_service",
)

SlackWebhookRequest = schemas.SlackWebhookRequest
SlackTeamAuth = app_mention_module.SlackTeamAuth
SlackThreadBinding = app_mention_module.SlackThreadBinding
SlackAppMentionService = app_mention_module.SlackAppMentionService


class FakeSlackClient:
    instances: list["FakeSlackClient"] = []

    def __init__(self, bot_access_token: str, team_id: str) -> None:
        self.bot_access_token = bot_access_token
        self.team_id = team_id
        self.post_message = AsyncMock()
        self.__class__.instances.append(self)


class FakeResponder:
    def __init__(self) -> None:
        self.finish = AsyncMock()
        self.fail = AsyncMock()
        self.on_node = AsyncMock()
        self.on_sources = AsyncMock()
        self.append_answer_markdown = AsyncMock()


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _make_request(
    *,
    raw_text: str,
    slack_user_id: str = "U123",
    team_id: str = "T123",
    channel_id: str = "C123",
    event_ts: str = "1712741200.000100",
    thread_ts: str | None = None,
):
    event = {
        "type": "app_mention",
        "channel": channel_id,
        "user": slack_user_id,
        "text": raw_text,
        "ts": event_ts,
    }
    if thread_ts is not None:
        event["thread_ts"] = thread_ts

    return SlackWebhookRequest.from_raw(
        wrapper_type="event_callback",
        team_id=team_id,
        event=event,
    )


class SlackAppMentionServiceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeSlackClient.instances.clear()
        self.run_in_threadpool_patcher = patch.object(
            app_mention_module,
            "run_in_threadpool",
            _run_immediately,
        )
        self.slack_client_patcher = patch.object(
            app_mention_module,
            "SlackApiClientWrapper",
            FakeSlackClient,
        )
        self.run_in_threadpool_patcher.start()
        self.slack_client_patcher.start()
        self.addCleanup(self.run_in_threadpool_patcher.stop)
        self.addCleanup(self.slack_client_patcher.stop)
        self.service = SlackAppMentionService()
        self.team_auth = SlackTeamAuth(bot_access_token="xoxb-test", bot_user_id="UBOT")

    async def test_posts_empty_query_message_when_only_bot_mention(self) -> None:
        with patch.object(self.service, "_load_team_auth_sync", lambda team_id: self.team_auth):
            await self.service.handle(request=_make_request(raw_text="<@UBOT>"))

        client = FakeSlackClient.instances[0]
        client.post_message.assert_awaited_once_with(
            channel="C123",
            thread_ts="1712741200.000100",
            text=app_mention_module.EMPTY_QUERY_MESSAGE,
        )

    async def test_posts_unmapped_user_message(self) -> None:
        with (
            patch.object(self.service, "_load_team_auth_sync", lambda team_id: self.team_auth),
            patch.object(self.service, "_find_internal_user_id_sync", lambda slack_user_id: None),
        ):
            await self.service.handle(request=_make_request(raw_text="<@UBOT> hello"))

        client = FakeSlackClient.instances[0]
        client.post_message.assert_awaited_once_with(
            channel="C123",
            thread_ts="1712741200.000100",
            text=app_mention_module.UNMAPPED_USER_MESSAGE,
        )

    async def test_blocks_thread_owner_mismatch(self) -> None:
        with (
            patch.object(self.service, "_load_team_auth_sync", lambda team_id: self.team_auth),
            patch.object(self.service, "_find_internal_user_id_sync", lambda slack_user_id: 7),
            patch.object(
                self.service,
                "_load_thread_binding_sync",
                lambda mention: SlackThreadBinding(session_id=uuid.uuid4(), chat_room_id=None, user_id=9),
            ),
        ):
            await self.service.handle(request=_make_request(raw_text="<@UBOT> hello"))

        client = FakeSlackClient.instances[0]
        client.post_message.assert_awaited_once_with(
            channel="C123",
            thread_ts="1712741200.000100",
            text=app_mention_module.THREAD_OWNER_MISMATCH_MESSAGE,
        )

    async def test_posts_missing_context_message(self) -> None:
        with (
            patch.object(self.service, "_load_team_auth_sync", lambda team_id: self.team_auth),
            patch.object(self.service, "_find_internal_user_id_sync", lambda slack_user_id: 7),
            patch.object(self.service, "_load_thread_binding_sync", lambda mention: None),
            patch.object(self.service, "_load_global_context_sync", lambda user_id: None),
        ):
            await self.service.handle(request=_make_request(raw_text="<@UBOT> hello"))

        client = FakeSlackClient.instances[0]
        client.post_message.assert_awaited_once_with(
            channel="C123",
            thread_ts="1712741200.000100",
            text=app_mention_module.MISSING_CONTEXT_MESSAGE,
        )

    async def test_finishes_responder_and_attaches_chat_room_on_stream_success(self) -> None:
        responder = FakeResponder()
        session_id = uuid.uuid4()
        attach_chat_room = Mock()
        run_chat_stream = AsyncMock(return_value=("final answer", [{"title": "Doc"}]))
        start_responder = AsyncMock(return_value=responder)

        with (
            patch.object(self.service, "_load_team_auth_sync", lambda team_id: self.team_auth),
            patch.object(self.service, "_find_internal_user_id_sync", lambda slack_user_id: 7),
            patch.object(self.service, "_load_thread_binding_sync", lambda mention: None),
            patch.object(
                self.service,
                "_load_global_context_sync",
                lambda user_id: SimpleNamespace(user_id=user_id),
            ),
            patch.object(self.service, "_ensure_thread_binding_sync", lambda mention, user_id: session_id),
            patch.object(self.service, "_run_chat_stream", run_chat_stream),
            patch.object(self.service, "_attach_chat_room_if_ready_sync", attach_chat_room),
            patch.object(app_mention_module.SlackPlanResponder, "start", start_responder),
        ):
            await self.service.handle(request=_make_request(raw_text="<@UBOT> hello"))

        start_responder.assert_awaited_once()
        run_chat_stream.assert_awaited_once()
        responder.finish.assert_awaited_once_with(answer="final answer", sources=[{"title": "Doc"}])
        responder.fail.assert_not_awaited()
        attach_chat_room.assert_called_once()
        self.assertEqual(attach_chat_room.call_args.args[1], session_id)
        self.assertEqual(attach_chat_room.call_args.args[2], 7)

    async def test_fails_responder_and_reraises_stream_errors(self) -> None:
        responder = FakeResponder()
        session_id = uuid.uuid4()
        run_chat_stream = AsyncMock(side_effect=RuntimeError("boom"))
        attach_chat_room = Mock()
        start_responder = AsyncMock(return_value=responder)

        with (
            patch.object(self.service, "_load_team_auth_sync", lambda team_id: self.team_auth),
            patch.object(self.service, "_find_internal_user_id_sync", lambda slack_user_id: 7),
            patch.object(self.service, "_load_thread_binding_sync", lambda mention: None),
            patch.object(
                self.service,
                "_load_global_context_sync",
                lambda user_id: SimpleNamespace(user_id=user_id),
            ),
            patch.object(self.service, "_ensure_thread_binding_sync", lambda mention, user_id: session_id),
            patch.object(self.service, "_run_chat_stream", run_chat_stream),
            patch.object(self.service, "_attach_chat_room_if_ready_sync", attach_chat_room),
            patch.object(app_mention_module.SlackPlanResponder, "start", start_responder),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                await self.service.handle(request=_make_request(raw_text="<@UBOT> hello"))

        responder.fail.assert_awaited_once_with(app_mention_module.STREAM_FAILED_MESSAGE)
        responder.finish.assert_not_awaited()
        attach_chat_room.assert_not_called()
