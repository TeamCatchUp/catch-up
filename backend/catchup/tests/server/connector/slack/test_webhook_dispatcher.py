from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from catchup.server.connector.slack import schemas
from catchup.sync.ingress import slack as dispatcher

SlackWebhookRequest = schemas.SlackWebhookRequest


def _make_request(
    *,
    wrapper_type: str = "event_callback",
    team_id: str = "T123",
    event: dict[str, object] | None = None,
    challenge: str | None = None,
):
    return SlackWebhookRequest.from_raw(
        wrapper_type=wrapper_type,
        team_id=team_id,
        event=event,
        challenge=challenge,
    )


class HandleSlackWebhookTests(IsolatedAsyncioTestCase):
    async def test_returns_url_verification_challenge(self) -> None:
        response = await dispatcher.handle_slack_webhook(
            request=_make_request(
                wrapper_type="url_verification",
                event=None,
                challenge="challenge-token",
            )
        )

        self.assertEqual(response.challenge, "challenge-token")

    async def test_delegates_supported_metadata_events(self) -> None:
        expected = SimpleNamespace(status="processed", event_type="channel_created")
        handle_metadata_event = AsyncMock(return_value=expected)

        with patch.object(dispatcher, "handle_metadata_event", handle_metadata_event):
            request = _make_request(event={"type": "channel_created", "channel": {"id": "C123"}})
            response = await dispatcher.handle_slack_webhook(request=request)

        self.assertIs(response, expected)
        handle_metadata_event.assert_awaited_once_with(request)

    async def test_schedules_app_mention_and_returns_accepted(self) -> None:
        schedule_app_mention = Mock()

        with patch.object(dispatcher, "schedule_app_mention", schedule_app_mention):
            request = _make_request(
                event={
                    "type": "app_mention",
                    "channel": "C123",
                    "user": "U123",
                    "text": "<@BOT> hello",
                    "ts": "1712741200.000100",
                }
            )
            response = await dispatcher.handle_slack_webhook(request=request)

        schedule_app_mention.assert_called_once_with(request)
        self.assertEqual(response.status, "accepted")
        self.assertEqual(response.event_type, "app_mention")

    async def test_schedules_direct_message_chat_and_skips_incremental(self) -> None:
        schedule_app_mention = Mock()
        handle_incremental_event = AsyncMock()

        with (
            patch.object(dispatcher, "schedule_app_mention", schedule_app_mention),
            patch.object(dispatcher, "_handle_incremental_event", handle_incremental_event),
        ):
            request = _make_request(
                event={
                    "type": "message",
                    "channel": "D123",
                    "channel_type": "im",
                    "user": "U123",
                    "text": "hello from dm",
                    "ts": "1712741200.000100",
                }
            )
            response = await dispatcher.handle_slack_webhook(request=request)

        schedule_app_mention.assert_called_once_with(request)
        handle_incremental_event.assert_not_awaited()
        self.assertEqual(response.status, "accepted")
        self.assertEqual(response.event_type, "message")

    async def test_non_chat_direct_messages_stay_out_of_chat_diversion(self) -> None:
        cases = [
            (
                "message_changed",
                {
                    "type": "message",
                    "channel": "D123",
                    "channel_type": "im",
                    "subtype": "message_changed",
                    "user": "U123",
                    "text": "edited",
                    "ts": "1712741200.000100",
                },
            ),
            (
                "missing_text",
                {
                    "type": "message",
                    "channel": "D123",
                    "channel_type": "im",
                    "user": "U123",
                    "ts": "1712741200.000100",
                },
            ),
            (
                "mpim",
                {
                    "type": "message",
                    "channel": "D123",
                    "channel_type": "mpim",
                    "user": "U123",
                    "text": "hello group",
                    "ts": "1712741200.000100",
                },
            ),
            (
                "bot_message",
                {
                    "type": "message",
                    "channel": "D123",
                    "channel_type": "im",
                    "user": "U123",
                    "bot_id": "B123",
                    "text": "hello from bot",
                    "ts": "1712741200.000100",
                },
            ),
        ]

        for label, event in cases:
            with self.subTest(label=label):
                schedule_app_mention = Mock()
                expected = SimpleNamespace(status="ignored", reason=label)
                handle_incremental_event = AsyncMock(return_value=expected)

                with (
                    patch.object(dispatcher, "schedule_app_mention", schedule_app_mention),
                    patch.object(dispatcher, "_handle_incremental_event", handle_incremental_event),
                ):
                    request = _make_request(event=event)
                    response = await dispatcher.handle_slack_webhook(request=request)

                schedule_app_mention.assert_not_called()
                handle_incremental_event.assert_awaited_once_with(request)
                self.assertIs(response, expected)

    async def test_dispatches_message_events_to_incremental_service(self) -> None:
        dispatch_changes = AsyncMock(
            return_value=SimpleNamespace(record_keys=["slack:C123:1712741200.000100"], blocked_count=0)
        )

        with (
            patch.object(
                dispatcher,
                "resolve_slack_event",
                lambda *, team_id, event: SimpleNamespace(changes=["change-1"], reason=None),
            ),
            patch.object(
                dispatcher,
                "get_incremental_service",
                lambda: SimpleNamespace(dispatch_changes=dispatch_changes),
            ),
        ):
            response = await dispatcher.handle_slack_webhook(
                request=_make_request(
                    event={
                        "type": "message",
                        "channel": "C123",
                        "ts": "1712741200.000100",
                        "text": "hello",
                    }
                )
            )

        dispatch_changes.assert_awaited_once_with(changes=["change-1"])
        self.assertEqual(response.status, "accepted")
        self.assertEqual(response.event_type, "message")
        self.assertEqual(response.record_keys, ["slack:C123:1712741200.000100"])
        self.assertIsNone(response.blocked_count)

    async def test_ignores_unknown_wrapper_types(self) -> None:
        response = await dispatcher.handle_slack_webhook(
            request=_make_request(wrapper_type="something_else", event={"type": "app_mention"})
        )

        self.assertEqual(response.status, "ignored")
        self.assertEqual(response.wrapper_type, "something_else")
        self.assertIsNone(response.reason)

    async def test_ignores_unsupported_event_types(self) -> None:
        response = await dispatcher.handle_slack_webhook(
            request=_make_request(
                event={
                    "type": "reaction_added",
                    "item": {"type": "message"},
                }
            )
        )

        self.assertEqual(response.status, "ignored")
        self.assertEqual(response.event_type, "reaction_added")
        self.assertEqual(response.reason, "unsupported_event")
