from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from typing import Protocol
from typing import TypeVar

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)


class ChannelTalkCredentialsStore(Protocol):
    def get_connection(
        self,
        channel_id: str | None = None,
    ) -> ChannelTalkCredentialsRecord | None: ...

    def list_connections(self) -> list[ChannelTalkCredentialsRecord]: ...

    def upsert_connection(
        self,
        payload: ChannelTalkCredentialsUpsert,
    ) -> ChannelTalkCredentialsRecord | None: ...

    def delete_connection(self, channel_id: str | None = None) -> bool: ...

    def commit(self) -> None: ...


StoreReturnT = TypeVar("StoreReturnT")


class ChannelTalkInstallAuthAdapter:
    """기존 Channel Talk client/repository 구현을 install-auth port 뒤로 감싸는 adapter."""

    def __init__(
        self,
        *,
        store: ChannelTalkCredentialsStore,
        client: ChannelTalkCoreApiClient | None = None,
    ) -> None:
        self.store = store
        self.client = client or ChannelTalkCoreApiClient()

    async def validate_credentials(
        self,
        request: ChannelTalkConnectRequest,
    ) -> ChannelTalkCurrentChannel:
        return await self.client.get_current_channel(
            access_key=request.access_key,
            access_secret=request.access_secret,
        )

    async def connect(
        self,
        *,
        request: ChannelTalkConnectRequest,
        validated_target: ChannelTalkCurrentChannel,
        verified_at: datetime,
    ) -> ChannelTalkCredentialsStatus:
        payload = ChannelTalkCredentialsUpsert(
            access_key=request.access_key,
            access_secret=request.access_secret,
            webhook_token=request.webhook_token,
            current_channel=validated_target,
            credential_last_verified_at=verified_at,
        )
        stored_record = await self._run_store(
            self.store.upsert_connection,
            payload,
            action="persist Channel Talk credentials",
        )
        await self._run_store(
            self.store.commit,
            action="commit Channel Talk credentials",
        )
        return ChannelTalkCredentialsStatus.from_record(stored_record or payload.to_record())

    async def get_status(self) -> ChannelTalkCredentialsStatus:
        record = await self._run_store(
            self.store.get_connection,
            action="load Channel Talk credentials",
        )
        return ChannelTalkCredentialsStatus.from_record(record)

    async def list_statuses(self) -> list[ChannelTalkCredentialsStatus]:
        records = await self._run_store(
            self.store.list_connections,
            action="list Channel Talk credentials",
        )
        return [ChannelTalkCredentialsStatus.from_record(record) for record in records]

    async def uninstall(
        self,
        channel_id: str | None = None,
    ) -> ChannelTalkUninstallResult:
        if not channel_id:
            raise ChannelTalkValidationError("channel_id is required")

        removed = await self._run_store(
            self.store.delete_connection,
            channel_id,
            action="delete Channel Talk credentials",
        )
        await self._run_store(
            self.store.commit,
            action="commit Channel Talk credentials deletion",
        )
        return ChannelTalkUninstallResult(removed=bool(removed))

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
