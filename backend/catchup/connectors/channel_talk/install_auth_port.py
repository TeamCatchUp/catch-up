from __future__ import annotations

from datetime import datetime
from typing import Protocol
from typing import TypeVar

RequestT = TypeVar("RequestT")
ValidatedT = TypeVar("ValidatedT")
StatusT = TypeVar("StatusT")
UninstallResultT = TypeVar("UninstallResultT")


class InstallAuthPort(Protocol[RequestT, ValidatedT, StatusT, UninstallResultT]):
    """설치 인증에 필요한 최소 계약만 노출해 connector별 구현을 교체 가능하게 만든다."""

    async def validate_credentials(self, request: RequestT) -> ValidatedT: ...

    async def connect(
        self,
        *,
        request: RequestT,
        validated_target: ValidatedT,
        verified_at: datetime,
    ) -> StatusT: ...

    async def get_status(self) -> StatusT: ...

    async def uninstall(self) -> UninstallResultT: ...
