from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Protocol
from typing import TypeVar

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.channel_talk.client import ChannelTalkApiClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.schemas import ChannelTalkConnectRequest
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsRecord
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsStatus
from catchup.connectors.channel_talk.schemas import ChannelTalkCredentialsUpsert
from catchup.connectors.channel_talk.schemas import ChannelTalkCurrentChannel
from catchup.connectors.channel_talk.schemas import ChannelTalkUninstallResult


class ChannelTalkCredentialsStore(Protocol):
    def get_connection(self) -> ChannelTalkCredentialsRecord | None: ...

    def upsert_connection(
        self,
        payload: ChannelTalkCredentialsUpsert,
    ) -> ChannelTalkCredentialsRecord | None: ...

    def delete_connection(self) -> bool: ...

    def commit(self) -> None: ...


StoreReturnT = TypeVar("StoreReturnT")


class ChannelTalkCredentialsService:
    def __init__(
        self,
        store: ChannelTalkCredentialsStore,
        client: ChannelTalkApiClient | None = None,
    ) -> None:
        self.store = store
        self.client = client or ChannelTalkApiClient()

    async def connect(
        self,
        request: ChannelTalkConnectRequest,
    ) -> ChannelTalkCredentialsStatus:
        # 1. 저장된 credential을 검증한다.
        current_channel = await self._get_current_channel(request)

        # 2. 마지막 검증 시각을 기록한다.
        verified_at = datetime.now(timezone.utc)

        # 3. 검증된 channel 정보와 입력한 토큰을 저장용 payload로 묶는다.
        payload = ChannelTalkCredentialsUpsert(
            access_key=request.access_key,
            access_secret=request.access_secret,
            webhook_token=request.webhook_token,
            current_channel=current_channel,
            credential_last_verified_at=verified_at,
        )

        # 4. 저장소에 upsert 한 뒤, service가 트랜잭션 commit을 확정한다.
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

    async def validate_credentials(
        self,
        request: ChannelTalkConnectRequest,
    ) -> ChannelTalkCurrentChannel:
        return await self._get_current_channel(request)

    async def get_status(self) -> ChannelTalkCredentialsStatus:
        record = await self._run_store(
            self.store.get_connection,
            action="load Channel Talk credentials",
        )
        return ChannelTalkCredentialsStatus.from_record(record)

    async def uninstall(self) -> ChannelTalkUninstallResult:
        removed = await self._run_store(
            self.store.delete_connection,
            action="delete Channel Talk credentials",
        )
        await self._run_store(
            self.store.commit,
            action="commit Channel Talk credentials deletion",
        )
        return ChannelTalkUninstallResult(removed=bool(removed))

    async def _get_current_channel(
        self,
        connect_request: ChannelTalkConnectRequest,
    ) -> ChannelTalkCurrentChannel:
        return await self.client.get_current_channel(
            access_key=connect_request.access_key,
            access_secret=connect_request.access_secret,
        )

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
