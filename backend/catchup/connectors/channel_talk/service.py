from __future__ import annotations

from typing import cast

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.document_space.client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.documents_install_auth_adapter import (
    ChannelTalkDocumentCredentialsStore,
)
from catchup.connectors.channel_talk.documents_install_auth_adapter import (
    ChannelTalkDocumentInstallAuthAdapter,
)
from catchup.connectors.channel_talk.install_auth_adapter import (
    ChannelTalkCredentialsStore,
)
from catchup.connectors.channel_talk.install_auth_adapter import (
    ChannelTalkInstallAuthAdapter,
)
from catchup.connectors.channel_talk.install_auth_application import (
    ConnectorInstallAuthApplication,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentUninstallResult,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace,
)


class ChannelTalkCredentialsService:
    """Channel Talk 설치 인증 흐름을 generic connector application에 위임하는 얇은 facade."""

    def __init__(
        self,
        store: ChannelTalkCredentialsStore,
        client: ChannelTalkCoreApiClient | None = None,
        application: ConnectorInstallAuthApplication[
            ChannelTalkConnectRequest,
            ChannelTalkCurrentChannel,
            ChannelTalkCredentialsStatus,
            ChannelTalkUninstallResult,
        ]
        | None = None,
    ) -> None:
        # 검증/저장/삭제 순서를 connector-local application이 고정한다.
        self.application = application or ConnectorInstallAuthApplication(
            port=ChannelTalkInstallAuthAdapter(
                store=store,
                client=client,
            )
        )
        self._port = cast(ChannelTalkInstallAuthAdapter, self.application.port)

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

    async def list_statuses(self) -> list[ChannelTalkCredentialsStatus]:
        return await self._port.list_statuses()

    async def uninstall(
        self,
        channel_id: str,
    ) -> ChannelTalkUninstallResult:
        return await self._port.uninstall(channel_id)


class ChannelTalkDocumentCredentialsService:
    def __init__(
        self,
        store: ChannelTalkDocumentCredentialsStore,
        client: ChannelTalkDocumentsApiClient | None = None,
        application: ConnectorInstallAuthApplication[
            ChannelTalkDocumentConnectRequest,
            ChannelTalkDocumentSpace,
            ChannelTalkDocumentCredentialsStatus,
            ChannelTalkDocumentUninstallResult,
        ]
        | None = None,
    ) -> None:
        adapter = ChannelTalkDocumentInstallAuthAdapter(
            store=store,
            client=client,
        )
        self.application = application or ConnectorInstallAuthApplication(
            port=adapter,
        )
        self._port = cast(ChannelTalkDocumentInstallAuthAdapter, self.application.port)

    async def connect(
        self,
        request: ChannelTalkDocumentConnectRequest,
    ) -> ChannelTalkDocumentCredentialsStatus:
        return await self.application.connect(request)

    async def validate_credentials(
        self,
        request: ChannelTalkDocumentConnectRequest,
    ) -> ChannelTalkDocumentSpace:
        return await self.application.validate_credentials(request)

    async def validate_connection(
        self,
        request: ChannelTalkDocumentConnectRequest,
    ) -> ChannelTalkDocumentCredentialsStatus:
        return await self._port.validate_connection(request)

    async def get_status(self) -> ChannelTalkDocumentCredentialsStatus:
        return await self.application.get_status()

    async def list_statuses(self) -> list[ChannelTalkDocumentCredentialsStatus]:
        return await self._port.list_statuses()

    async def uninstall(
        self,
        space_id: str,
    ) -> ChannelTalkDocumentUninstallResult:
        return await self._port.uninstall(space_id)
