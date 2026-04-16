from __future__ import annotations

from typing import Any


class ChannelTalkError(Exception):
    code = "channel_talk_error"
    status_code = 500
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        retryable: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.status_code = self.status_code if status_code is None else status_code
        self.retryable = self.retryable if retryable is None else retryable
        self.metadata = dict(metadata or {})


class ChannelTalkValidationError(ChannelTalkError):
    code = "invalid_request"
    status_code = 400


class ChannelTalkAuthenticationError(ChannelTalkError):
    code = "invalid_credentials"
    status_code = 401


class ChannelTalkConflictError(ChannelTalkError):
    code = "connection_conflict"
    status_code = 409


class ChannelTalkPayloadError(ChannelTalkError):
    code = "invalid_upstream_payload"
    status_code = 502
    retryable = True


class ChannelTalkUpstreamError(ChannelTalkError):
    code = "upstream_error"
    status_code = 502
    retryable = True


class ChannelTalkTimeoutError(ChannelTalkUpstreamError):
    code = "upstream_timeout"
    status_code = 503


class ChannelTalkRateLimitError(ChannelTalkUpstreamError):
    code = "upstream_rate_limited"
    status_code = 429

    def __init__(
        self,
        message: str = "Channel Talk API rate limit exceeded",
        *,
        retry_after: int = 60,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=429,
            retryable=True,
            metadata=metadata,
        )
        self.retry_after = retry_after


class ChannelTalkPersistenceError(ChannelTalkError):
    code = "persistence_failed"
    status_code = 500
