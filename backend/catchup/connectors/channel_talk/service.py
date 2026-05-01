from __future__ import annotations

from typing import cast

from catchup.connector_core.adapters.channel_talk.documents_install_auth_adapter import (
    ChannelTalkDocumentCredentialsStore,
)
from catchup.connector_core.adapters.channel_talk.documents_install_auth_adapter import (
    ChannelTalkDocumentInstallAuthAdapter,
)
from catchup.connector_core.adapters.channel_talk.documents_metadata_sync_adapter import (
    ChannelTalkDocumentMetadataStore,
)
from catchup.connector_core.adapters.channel_talk.documents_metadata_sync_adapter import (
    ChannelTalkDocumentMetadataSyncAdapter,
)
from catchup.connector_core.adapters.channel_talk.install_auth_adapter import (
    ChannelTalkCredentialsStore,
)
from catchup.connector_core.adapters.channel_talk.install_auth_adapter import (
    ChannelTalkInstallAuthAdapter,
)
from catchup.connector_core.adapters.channel_talk.metadata_sync_adapter import (
    ChannelTalkMetadataStore,
)
from catchup.connector_core.adapters.channel_talk.metadata_sync_adapter import (
    ChannelTalkMetadataSyncAdapter,
)
from catchup.connector_core.application.install_auth import (
    ConnectorInstallAuthApplication,
)
from catchup.connector_core.application.metadata_sync import (
    ConnectorMetadataSyncApplication,
)
from catchup.connectors.channel_talk.core_api_client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.documents_client import (
    ChannelTalkDocumentsApiClient,
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
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkMetadataSyncRequest,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkMetadataSyncResult,
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
    ChannelTalkDocumentMetadataSyncRequest,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentMetadataSyncResult,
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
        # 실제 검증/저장/삭제 orchestration은 connector_core의 공통 application + adapter 조합으로 이동시켜 재사용 기반을 만든다.
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


class ChannelTalkMetadataSyncService:
    """Channel Talk post-connect metadata 동기화를 전담하는 facade."""

    def __init__(
        self,
        store: ChannelTalkMetadataStore,
        client: ChannelTalkCoreApiClient | None = None,
        application: ConnectorMetadataSyncApplication | None = None,
    ) -> None:
        self.application = application or ConnectorMetadataSyncApplication(
            port=ChannelTalkMetadataSyncAdapter(
                store=store,
                client=client,
            )
        )

    async def sync_metadata(
        self,
        request: ChannelTalkMetadataSyncRequest,
    ) -> ChannelTalkMetadataSyncResult:
        result = await self.application.sync_metadata(request.to_core_request())
        return ChannelTalkMetadataSyncResult.from_core_result(result)

    async def sync_target(
        self,
        channel_id: str,
    ) -> ChannelTalkMetadataSyncResult:
        return await self.sync_metadata(
            ChannelTalkMetadataSyncRequest(channel_id=channel_id)
        )

    async def sync_channel(
        self,
        channel_id: str,
    ) -> ChannelTalkMetadataSyncResult:
        return await self.sync_target(channel_id)


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


class ChannelTalkDocumentMetadataSyncService:
    def __init__(
        self,
        store: ChannelTalkDocumentMetadataStore,
        client: ChannelTalkDocumentsApiClient | None = None,
        application: ConnectorMetadataSyncApplication | None = None,
    ) -> None:
        self.application = application or ConnectorMetadataSyncApplication(
            port=ChannelTalkDocumentMetadataSyncAdapter(
                store=store,
                client=client,
            )
        )

    async def sync_metadata(
        self,
        request: ChannelTalkDocumentMetadataSyncRequest,
    ) -> ChannelTalkDocumentMetadataSyncResult:
        result = await self.application.sync_metadata(request.to_core_request())
        return ChannelTalkDocumentMetadataSyncResult.from_core_result(result)

    async def sync_target(
        self,
        channel_id: str,
    ) -> ChannelTalkDocumentMetadataSyncResult:
        return await self.sync_metadata(
            ChannelTalkDocumentMetadataSyncRequest(channel_id=channel_id)
        )

    async def sync_space(
        self,
        channel_id: str,
        space_id: str,
    ) -> ChannelTalkDocumentMetadataSyncResult:
        return await self.sync_metadata(
            ChannelTalkDocumentMetadataSyncRequest(
                channel_id=channel_id,
                space_id=space_id,
            )
        )

    async def sync_channel(
        self,
        channel_id: str,
    ) -> ChannelTalkDocumentMetadataSyncResult:
        return await self.sync_target(channel_id)
