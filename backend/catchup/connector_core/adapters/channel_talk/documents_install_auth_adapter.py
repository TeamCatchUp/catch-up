from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from typing import Protocol
from typing import TypeVar

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.channel_talk.documents_client import (
    ChannelTalkDocumentsApiClient,
)
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentUninstallResult,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace,
)


class ChannelTalkDocumentCredentialsStore(Protocol):
    def get_base_connection(self) -> ChannelTalkCredentialsRecord | None: ...

    def get_document_connection(
        self,
        channel_id: str | None = None,
        space_id: str | None = None,
    ) -> ChannelTalkDocumentCredentialsRecord | None: ...

    def list_document_connections(
        self,
        channel_id: str | None = None,
    ) -> list[ChannelTalkDocumentCredentialsRecord]: ...

    def upsert_document_connection(
        self,
        payload: ChannelTalkDocumentCredentialsUpsert,
    ) -> ChannelTalkDocumentCredentialsRecord | None: ...

    def delete_document_connection_by_space_id(self, space_id: str) -> bool: ...

    def commit(self) -> None: ...


StoreReturnT = TypeVar("StoreReturnT")


class ChannelTalkDocumentInstallAuthAdapter:
    def __init__(
        self,
        *,
        store: ChannelTalkDocumentCredentialsStore,
        client: ChannelTalkDocumentsApiClient | None = None,
    ) -> None:
        self.store = store
        self.client = client

    async def validate_credentials(
        self,
        request: ChannelTalkDocumentConnectRequest,
    ) -> ChannelTalkDocumentSpace:
        client = self.client or ChannelTalkDocumentsApiClient(
            access_key=request.access_key,
            access_secret=request.access_secret,
        )
        return await client.get_current_space()

    async def validate_connection(
        self,
        request: ChannelTalkDocumentConnectRequest,
    ) -> ChannelTalkDocumentCredentialsStatus:
        validated_target = await self.validate_credentials(request)
        base_connection = await self._load_base_connection()
        association_status = self._resolve_association_status(
            base_channel_id=base_connection.channel_id,
            space=validated_target,
        )
        return ChannelTalkDocumentCredentialsStatus(
            installed=False,
            channel_id=base_connection.channel_id,
            space_id=validated_target.space_id,
            space_name=validated_target.space_name,
            association_status=association_status,
        )

    async def connect(
        self,
        *,
        request: ChannelTalkDocumentConnectRequest,
        validated_target: ChannelTalkDocumentSpace,
        verified_at: datetime,
    ) -> ChannelTalkDocumentCredentialsStatus:
        base_connection = await self._load_base_connection()
        association_status = self._resolve_association_status(
            base_channel_id=base_connection.channel_id,
            space=validated_target,
        )
        payload = ChannelTalkDocumentCredentialsUpsert(
            channel_id=base_connection.channel_id,
            access_key=request.access_key,
            access_secret=request.access_secret,
            space=validated_target,
            credential_last_verified_at=verified_at,
            association_status=association_status,
        )
        stored_record = await self._run_store(
            self.store.upsert_document_connection,
            payload,
            action="persist Channel Talk Documents credentials",
        )
        await self._run_store(
            self.store.commit,
            action="commit Channel Talk Documents credentials",
        )
        return ChannelTalkDocumentCredentialsStatus.from_record(
            stored_record or payload.to_record()
        )

    async def get_status(self) -> ChannelTalkDocumentCredentialsStatus:
        record = await self._run_store(
            self.store.get_document_connection,
            action="load Channel Talk Documents credentials",
        )
        return ChannelTalkDocumentCredentialsStatus.from_record(record)

    async def list_statuses(self) -> list[ChannelTalkDocumentCredentialsStatus]:
        records = await self._run_store(
            self.store.list_document_connections,
            action="list Channel Talk Documents credentials",
        )
        return [ChannelTalkDocumentCredentialsStatus.from_record(record) for record in records]

    async def uninstall(
        self,
        space_id: str | None = None,
    ) -> ChannelTalkDocumentUninstallResult:
        if not space_id:
            raise ChannelTalkValidationError("space_id is required")

        removed = await self._run_store(
            self.store.delete_document_connection_by_space_id,
            space_id,
            action="delete Channel Talk Documents credentials",
        )
        await self._run_store(
            self.store.commit,
            action="commit Channel Talk Documents credentials deletion",
        )
        return ChannelTalkDocumentUninstallResult(removed=bool(removed))

    async def _load_base_connection(self) -> ChannelTalkCredentialsRecord:
        record = await self._run_store(
            self.store.get_base_connection,
            action="load Channel Talk credentials",
        )
        if record is None:
            raise ChannelTalkValidationError("Channel Talk credentials are not installed")
        return record

    @staticmethod
    def _resolve_association_status(
        *,
        base_channel_id: str,
        space: ChannelTalkDocumentSpace,
    ) -> ChannelTalkDocumentAssociationStatus:
        if space.channel_id != base_channel_id:
            raise ChannelTalkConflictError(
                "Channel Talk Documents space does not match the installed Channel Talk channel",
            )
        return ChannelTalkDocumentAssociationStatus.API_VERIFIED

    async def _run_store(
        self,
        operation: Callable[..., StoreReturnT],
        *args: Any,
        action: str,
    ) -> StoreReturnT:
        try:
            return await run_in_threadpool(operation, *args)
        except ChannelTalkError:
            raise
        except Exception as exc:
            raise ChannelTalkPersistenceError(f"Failed to {action}") from exc
