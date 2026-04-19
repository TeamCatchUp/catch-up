from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Callable
from typing import Generic

from catchup.connector_core.ports.install_auth import InstallAuthPort
from catchup.connector_core.ports.install_auth import RequestT
from catchup.connector_core.ports.install_auth import StatusT
from catchup.connector_core.ports.install_auth import UninstallResultT
from catchup.connector_core.ports.install_auth import ValidatedT


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectorInstallAuthApplication(Generic[RequestT, ValidatedT, StatusT, UninstallResultT]):
    """설치형 connector의 인증 흐름 순서를 공통화하는 application layer."""

    def __init__(
        self,
        *,
        port: InstallAuthPort[RequestT, ValidatedT, StatusT, UninstallResultT],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.port = port
        self.clock = clock or _utcnow

    async def connect(self, request: RequestT) -> StatusT:
        # 의도: "검증 -> 검증 시각 기록 -> 저장" 순서를 모든 설치형 connector가
        # 동일하게 따르도록 application layer에서 orchestration을 고정한다.
        validated_target = await self.port.validate_credentials(request)
        return await self.port.connect(
            request=request,
            validated_target=validated_target,
            verified_at=self.clock(),
        )

    async def validate_credentials(self, request: RequestT) -> ValidatedT:
        return await self.port.validate_credentials(request)

    async def get_status(self) -> StatusT:
        return await self.port.get_status()

    async def uninstall(self) -> UninstallResultT:
        return await self.port.uninstall()
