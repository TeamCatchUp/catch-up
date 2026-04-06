from __future__ import annotations

from typing import Any

from catchup.db.models import SyncConnector
from catchup.exceptions.base_exception import BaseDomainException


class BaseSyncException(BaseDomainException):
    code = "sync_api_error"
    default_message = "Sync API error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message or self.default_message)
        if code is not None:
            self.code = code
        self.metadata = dict(metadata or {})

    def to_detail(
        self,
        *,
        connector: SyncConnector | None = None,
        scope_id: str | None = None,
    ) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }

        if connector is not None:
            detail["connector"] = connector
        if scope_id is not None:
            detail["scope_id"] = scope_id
        if self.metadata:
            detail["metadata"] = self.metadata

        return detail


class SyncRequestException(BaseSyncException):
    code = "invalid_request"
    default_message = "Invalid sync request"

    def __init__(
        self,
        message: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code or self.code,
            metadata=metadata,
        )


class UnsupportedConnectorException(SyncRequestException):
    code = "unsupported_sync_connector"
    default_message = "Unsupported sync connector"

    def __init__(
        self,
        *,
        requested_connector: str,
        registered_connectors: list[str],
        message: str | None = None,
    ) -> None:
        super().__init__(message=message or self.default_message, code=self.code)
        self.requested_connector = requested_connector
        self.registered_connectors = registered_connectors

    def to_detail(
        self,
        *,
        connector: SyncConnector | None = None,
        scope_id: str | None = None,
    ) -> dict[str, Any]:
        detail = super().to_detail(
            connector=connector,
            scope_id=scope_id,
        )
        detail["requested_connector"] = self.requested_connector
        detail["registered_connectors"] = self.registered_connectors
        return detail


class SyncConnectorException(BaseSyncException):
    code = "connector_unavailable"
    default_message = "Sync connector unavailable"

    def __init__(
        self,
        message: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code or self.code,
            metadata=metadata,
        )


class SyncInternalException(BaseSyncException):
    code = "internal_error"
    default_message = "Sync internal error"

    def __init__(
        self,
        message: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code or self.code,
            metadata=metadata,
        )


class RedisStreamInitializationException(SyncInternalException):
    def __init__(
        self,
        message: str = "redis stream initialization failed",
        *,
        metadata: dict[str, Any] | None = None,
        code: str = "stream_runtime_init_failed",
    ) -> None:
        super().__init__(
            message=message,
            metadata=metadata,
            code=code,
        )


class RedisStreamPublishException(SyncInternalException):
    def __init__(
        self,
        message: str = "redis stream publish failed",
        *,
        metadata: dict[str, Any] | None = None,
        code: str = "stream_publish_failed",
    ) -> None:
        super().__init__(
            message=message,
            metadata=metadata,
            code=code,
        )
