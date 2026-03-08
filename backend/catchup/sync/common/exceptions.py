from __future__ import annotations

from typing import Any

from catchup.db.models import SyncConnector


class SyncAPIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
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


class SyncRequestError(SyncAPIError):
    def __init__(
        self,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
        code: str = "invalid_request",
    ) -> None:
        super().__init__(
            status_code=400,
            code=code,
            message=message,
            metadata=metadata,
        )


class SyncConnectorError(SyncAPIError):
    def __init__(
        self,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
        code: str = "connector_unavailable",
    ) -> None:
        super().__init__(
            status_code=400,
            code=code,
            message=message,
            metadata=metadata,
        )


class SyncInternalError(SyncAPIError):
    def __init__(
        self,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
        code: str = "internal_error",
    ) -> None:
        super().__init__(
            status_code=500,
            code=code,
            message=message,
            metadata=metadata,
        )
