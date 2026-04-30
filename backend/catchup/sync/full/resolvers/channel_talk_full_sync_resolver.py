from __future__ import annotations

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.connectors.channel_talk.full_sync_helper import (
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    build_channel_talk_channel_metadata,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    build_channel_talk_document_space_metadata,
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
        # 1. 저장된 Channel Talk base connection을 먼저 확인한다.
        # scope_id가 비어 있으면 이 connection의 channel_id가 요청 scope가 된다.
        connection = await run_in_threadpool(load_channel_talk_connection)
        if connection is None:
            raise SyncRequestException(
                "channel_talk is not connected",
                metadata={"scope_id": request.scope_id},
            )

        try:
            channel_id = (
                require_channel_talk_channel_id(
                    request.scope_id,
                    empty_message="scope_id is required",
                )
                if request.scope_id.strip()
                else connection.channel_id
            )
        except ValueError as exc:
            raise SyncRequestException(str(exc)) from exc

        if connection.channel_id != channel_id:
            raise SyncRequestException(
                "Stored Channel Talk credentials do not match the requested channel",
                metadata={
                    "scope_id": channel_id,
                    "channel_id": connection.channel_id,
                },
            )

        # 2. Channel Talk은 channel(UserChat)과 space(DocumentArticle) 두 target_type만 받는다.
        # user_chat/document_article 같은 runtime alias는 요청값으로 허용하지 않는다.
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

        # 3. channel target은 base connection만으로 항상 후보가 된다.
        # 요청 key는 (target_type, target_id)이므로 channel_id와 space_id가 같아도 충돌하지 않는다.
        channel_target = FullSyncTarget(
            target_type=SyncTargetType.CHANNEL,
            target_id=connection.channel_id,
            target_name=connection.channel_name,
            metadata=build_channel_talk_channel_metadata(channel_id),
        )
        targets_by_request_key: dict[tuple[SyncTargetType, str], FullSyncTarget] = {
            (SyncTargetType.CHANNEL, connection.channel_id): channel_target,
        }

        document_connection = None
        if any(
            target.target_type == SyncTargetType.SPACE for target in requested_targets
        ):
            # 4. space target을 요청한 경우에만 Documents connection을 조회한다.
            # channel-only Full Sync에서는 document 연결 여부가 실행 조건이 아니다.
            document_connection = await run_in_threadpool(
                load_channel_talk_document_connection,
                channel_id,
            )

        if (
            document_connection is not None
            and is_verified_channel_talk_document_connection(
                document_connection,
                channel_id=channel_id,
            )
        ):
            document_target = FullSyncTarget(
                target_type=SyncTargetType.SPACE,
                target_id=document_connection.space_id,
                target_name=document_connection.space_name,
                metadata={
                    **build_channel_talk_document_space_metadata(channel_id),
                    "space_id": document_connection.space_id,
                    "space_name": document_connection.space_name,
                },
            )
            targets_by_request_key[
                (SyncTargetType.SPACE, document_connection.space_id)
            ] = document_target

        # 5. 요청한 typed target이 후보 목록에 없으면 unknown target으로 실패한다.
        # 예: target_type=channel인데 space_id를 보냈거나, Documents가 미연결인 space 요청.
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

        # 6. 요청 순서를 유지해 FullSyncTarget을 반환한다. 중복은 이미 정규화됐지만
        # resolver 단에서도 tuple key 기준으로 한 번 더 방어한다.
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
    def _target_metadata(target: FullSyncRequestedTarget) -> dict[str, str]:
        return {
            "target_type": target.target_type.value,
            "target_id": target.target_id,
        }


_channel_talk_full_sync_target_resolver = ChannelTalkFullSyncTargetResolver()


def get_channel_talk_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _channel_talk_full_sync_target_resolver
