from __future__ import annotations

from unittest import TestCase

from catchup.sync.incremental.resolve import resolve_slack_event


class ResolveSlackEventTests(TestCase):
    def test_direct_message_channels_remain_unsupported(self) -> None:
        result = resolve_slack_event(
            team_id="T123",
            event={
                "type": "message",
                "channel": "D123",
                "channel_type": "im",
                "user": "U123",
                "text": "hello from dm",
                "ts": "1712741200.000100",
            },
        )

        self.assertEqual(result.changes, [])
        self.assertEqual(result.reason, "unsupported_channel")
