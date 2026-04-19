from __future__ import annotations

from catchup.connector_core.adapters.channel_talk.install_auth_adapter import (
    ChannelTalkCredentialsStore,
)
from catchup.connector_core.adapters.channel_talk.install_auth_adapter import (
    ChannelTalkInstallAuthAdapter,
)
from catchup.connector_core.application.install_auth import (
    ConnectorInstallAuthApplication,
)
from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.schemas import ChannelTalkConnectRequest
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsStatus
from catchup.connectors.channel_talk.schemas import ChannelTalkCurrentChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkUninstallResult


class ChannelTalkCredentialsService:
    """Channel Talk 설치 인증 흐름을 generic connector application에 위임하는 얇은 facade."""

    def __init__(
        self,
        store: ChannelTalkCredentialsStore,
        client: ChannelTalkApiClient | None = None,
        application: ConnectorInstallAuthApplication[
            ChannelTalkConnectRequest,
            ChannelTalkCurrentChannel,
            ChannelTalkCredentialsStatus,
            ChannelTalkUninstallResult,
        ]
        | None = None,
    ) -> None:
        # 실제 검증/저장/삭제 orchestration은 connector_core의 공통 application + adapter 조합으로 이동시켜 재사용 기반을 만든다.
        self.application = application or ConnectorInstallAuthApplication(
            port=ChannelTalkInstallAuthAdapter(
                store=store,
                client=client,
            )
        )

    async def connect(
        self,
        request: ChannelTalkConnectRequest,
    ) -> ChannelTalkCredentialsStatus:
        return await self.application.connect(request)

    async def validate_credentials(
        self,
        request: ChannelTalkConnectRequest,
    ) -> ChannelTalkCurrentChannel:
        return await self.application.validate_credentials(request)

    async def get_status(self) -> ChannelTalkCredentialsStatus:
        return await self.application.get_status()

    async def uninstall(self) -> ChannelTalkUninstallResult:
        return await self.application.uninstall()
