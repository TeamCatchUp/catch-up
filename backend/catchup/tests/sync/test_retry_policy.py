from __future__ import annotations

from datetime import timedelta
from unittest import TestCase

from botocore.exceptions import ConnectionClosedError
from botocore.exceptions import ConnectTimeoutError
from botocore.exceptions import EndpointConnectionError
from botocore.exceptions import ReadTimeoutError

from catchup.connectors.base.exceptions import ConnectorApiError
from catchup.connectors.base.exceptions import RateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.sync.common.retry_policy import is_retryable_sync_error
from catchup.sync.common.retry_policy import resolve_retry_delay


class ChannelTalkRetryPolicyTests(TestCase):
    def test_channel_talk_rate_limit_uses_common_retry_after_policy(self) -> None:
        exc = ChannelTalkRateLimitError(retry_after=37)

        self.assertIsInstance(exc, RateLimitError)
        self.assertIsInstance(exc, ConnectorApiError)
        self.assertTrue(is_retryable_sync_error(exc))
        self.assertEqual(
            resolve_retry_delay(
                exc=exc,
                attempt=1,
                base_delay_seconds=1,
                max_delay_seconds=10,
            ),
            timedelta(seconds=37),
        )

    def test_channel_talk_upstream_error_is_retryable_connector_api_error(self) -> None:
        exc = ChannelTalkUpstreamError(
            "Channel Talk API is temporarily unavailable",
            status_code=502,
        )

        self.assertIsInstance(exc, ConnectorApiError)
        self.assertTrue(is_retryable_sync_error(exc))


class BedrockTransportRetryPolicyTests(TestCase):
    def test_botocore_transport_errors_are_retryable(self) -> None:
        for exc in (
            ConnectionClosedError(endpoint_url="https://bedrock-runtime.example"),
            EndpointConnectionError(endpoint_url="https://bedrock-runtime.example"),
            ReadTimeoutError(endpoint_url="https://bedrock-runtime.example"),
            ConnectTimeoutError(endpoint_url="https://bedrock-runtime.example"),
        ):
            with self.subTest(exc=exc.__class__.__name__):
                self.assertTrue(is_retryable_sync_error(exc))
