from __future__ import annotations

import asyncio
from collections.abc import Awaitable

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.connectors.channel_talk.full_sync_helper import (
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    list_channel_talk_document_connections,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    ChannelTalkFullSyncTargetPlan,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncRequestedTarget
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import FullSyncTarget
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.full.targets import normalize_requested_targets

logger = structlog.get_logger(__name__)


class ChannelTalkFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:

        try:
            channel_id = require_channel_talk_channel_id(
                request.scope_id,
                empty_message="scope_id is required",
            )
        except ValueError as exc:
            raise SyncRequestException(str(exc)) from exc

        requested_targets = normalize_requested_targets(request.targets)
        invalid_targets = [
            self._target_metadata(target)
            for target in requested_targets
            if target.target_type not in {SyncTargetType.CHANNEL, SyncTargetType.SPACE}
        ]
        if invalid_targets:
            raise SyncRequestException(
                "requested targets contain invalid channel_talk target_type",
                metadata={
                    "channel_id": channel_id,
                    "expected_target_types": [
                        SyncTargetType.CHANNEL.value,
                        SyncTargetType.SPACE.value,
                    ],
                    "invalid_targets": invalid_targets,
                },
            )

        # base channel connection은 channel/space resolve 양쪽에서 필요하므로 하나의 task로 공유
        requested_target_types = {target.target_type for target in requested_targets}
        channel_connection_task = asyncio.create_task(
            run_in_threadpool(
                load_channel_talk_connection,
                channel_id,
            )
        )

        resolve_tasks: list[
            Awaitable[dict[tuple[SyncTargetType, str], FullSyncTarget]]
        ] = []
        if SyncTargetType.CHANNEL in requested_target_types:
            resolve_tasks.append(
                self._resolve_channel_target(
                    channel_id=channel_id,
                    channel_connection_task=channel_connection_task,
                )
            )
        if SyncTargetType.SPACE in requested_target_types:
            resolve_tasks.append(
                self._resolve_document_space_target(
                    channel_id=channel_id,
                    channel_connection_task=channel_connection_task,
                )
            )

        resolved_target_groups = await asyncio.gather(*resolve_tasks)

        targets_by_request_key: dict[tuple[SyncTargetType, str], FullSyncTarget] = {}
        for target_group in resolved_target_groups:
            targets_by_request_key.update(target_group)

        # 요청한 typed target이 후보에 없으면 명확히 unknown target으로 실패
        unknown_targets = [
            self._target_metadata(target)
            for target in requested_targets
            if (target.target_type, target.target_id) not in targets_by_request_key
        ]
        if unknown_targets:
            raise SyncRequestException(
                "requested targets contain unknown channel_talk targets",
                metadata={
                    "channel_id": channel_id,
                    "requested_targets": [
                        self._target_metadata(target) for target in requested_targets
                    ],
                    "invalid_targets": unknown_targets,
                },
            )

        resolved_targets: list[FullSyncTarget] = []
        seen_target_keys: set[tuple[SyncTargetType, str]] = set()
        for requested_target in requested_targets:
            key = (requested_target.target_type, requested_target.target_id)
            target = targets_by_request_key[key]
            if key in seen_target_keys:
                continue
            seen_target_keys.add(key)
            resolved_targets.append(target)

        logger.info(
            "channel_talk_full_sync_targets_resolved",
            channel_id=channel_id,
            requested_count=len(requested_targets),
            resolved_count=len(resolved_targets),
        )
        return FullSyncResolvedTargets(targets=resolved_targets)

    @staticmethod
    async def _resolve_channel_target(
        *,
        channel_id: str,
        channel_connection_task: asyncio.Task[ChannelTalkCredentialsRecord | None],
    ) -> dict[tuple[SyncTargetType, str], FullSyncTarget]:
        connection = await channel_connection_task
        if connection is None:
            raise SyncRequestException(
                "channel_talk is not connected for the requested channel",
                metadata={"scope_id": channel_id},
            )
        if connection.channel_id != channel_id:
            raise SyncRequestException(
                "Stored Channel Talk credentials do not match the requested channel",
                metadata={
                    "scope_id": channel_id,
                    "channel_id": connection.channel_id,
                },
            )

        target = ChannelTalkFullSyncTargetResolver._build_full_sync_target(
            ChannelTalkFullSyncTargetPlan.channel(
                channel_id=connection.channel_id,
                channel_name=connection.channel_name,
            )
        )
        return {
            (target.target_type, target.target_id): target,
        }

    @staticmethod
    async def _resolve_document_space_target(
        *,
        channel_id: str,
        channel_connection_task: asyncio.Task[ChannelTalkCredentialsRecord | None],
    ) -> dict[tuple[SyncTargetType, str], FullSyncTarget]:

        document_connections_task = asyncio.create_task(
            run_in_threadpool(
                list_channel_talk_document_connections,
                channel_id,
            )
        )
        connection, document_connections = await asyncio.gather(
            channel_connection_task,
            document_connections_task,
        )

        if connection is None:
            raise SyncRequestException(
                "channel_talk is not connected for the requested channel",
                metadata={"scope_id": channel_id},
            )
        if connection.channel_id != channel_id:
            raise SyncRequestException(
                "Stored Channel Talk credentials do not match the requested channel",
                metadata={
                    "scope_id": channel_id,
                    "channel_id": connection.channel_id,
                },
            )
        if not document_connections:
            raise SyncRequestException(
                "channel_talk documents is not connected for the requested channel",
                metadata={"channel_id": channel_id},
            )
        verified_document_connections = [
            document_connection
            for document_connection in document_connections
            if is_verified_channel_talk_document_connection(
                document_connection,
                channel_id=channel_id,
            )
        ]
        if not verified_document_connections:
            raise SyncRequestException(
                "channel_talk documents credentials are not API verified for the requested channel",
                metadata={"channel_id": channel_id},
            )

        targets = [
            ChannelTalkFullSyncTargetResolver._build_full_sync_target(
                ChannelTalkFullSyncTargetPlan.document_space(
                    channel_id=channel_id,
                    space_id=document_connection.space_id,
                    space_name=document_connection.space_name,
                )
            )
            for document_connection in verified_document_connections
        ]
        return {
            (target.target_type, target.target_id): target
            for target in targets
        }

    @staticmethod
    def _build_full_sync_target(
        plan: ChannelTalkFullSyncTargetPlan,
    ) -> FullSyncTarget:
        return FullSyncTarget(
            target_type=SyncTargetType(plan.target_type),
            target_id=plan.target_id,
            target_name=plan.target_name,
            metadata=plan.to_metadata(),
        )

    @staticmethod
    def _target_metadata(target: FullSyncRequestedTarget) -> dict[str, str]:
        return {
            "target_type": target.target_type.value,
            "target_id": target.target_id,
        }


_channel_talk_full_sync_target_resolver = ChannelTalkFullSyncTargetResolver()


def get_channel_talk_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _channel_talk_full_sync_target_resolver
