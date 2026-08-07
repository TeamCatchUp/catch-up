"""ChannelTalk user chat을 수집 계약 envelope로 옮긴다.

폴러가 하는 일은 두 가지다. 어떤 대화가 바뀌었는지 목록으로 좁히고, 바뀐
대화의 상세와 메시지를 모아 하나의 payload로 봉한다. payload 형식은 합성
데이터 빌더(`catchup/evaluation/build_channel_talk_payloads.py`)와 같다.
normalizer가 두 경로를 구분하지 못해야 실데이터와 합성 데이터의 파이프라인
결과를 서로 대조할 수 있기 때문이다.

여기서는 저장도 정규화도 하지 않는다. 원문을 읽어 계약 형태로 바꾸는 것까지가
이 어댑터의 책임이고, 그 다음은 러너가 이어받는다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone

import structlog

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (  # noqa: E501
    CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.contracts.source_change import SourceIdentityPayload
from catchup.knowledge_maintenance.domain.source_version import ChangeKind

logger = structlog.get_logger(__name__)

SOURCE_TYPE = "channel_talk"
ENTITY_TYPE = "user_chat"
PAYLOAD_SCHEMA_VERSION = 1

DEFAULT_STATES: tuple[str, ...] = ("opened", "closed", "snoozed")

# ordering_marker를 모르는 대화의 정렬 기준이다. 가장 오래된 것으로 두어
# limit이 걸려도 먼저 집히게 한다. 판단할 근거가 없는 대화를 뒤로 미루면
# 다음 폴링에서도 계속 밀려 영영 수집되지 않는다.
_UNKNOWN_MARKER = datetime.min.replace(tzinfo=timezone.utc)


class ChannelTalkUserChatPoller:
    """ChannelTalk user chat 변경을 SourceChangeEnvelope로 낸다."""

    def __init__(
        self,
        *,
        client: ChannelTalkCoreApiClient,
        access_key: str,
        access_secret: str,
        channel_id: str,
    ) -> None:
        self._client = client
        self._access_key = access_key
        self._access_secret = access_secret
        self._channel_id = channel_id

    async def poll(
        self,
        *,
        workspace_id: int,
        lookback_start: datetime,
        limit: int,
        max_pages: int,
        states: Sequence[str] = DEFAULT_STATES,
    ) -> list[SourceChangeEnvelope]:
        """lookback_start 이후 바뀐 대화를 수집 계약 envelope로 변환한다."""
        observed_at = datetime.now(timezone.utc)
        markers_by_chat_id = await self._list_changed_chats(
            lookback_start=lookback_start,
            max_pages=max_pages,
            states=states,
        )

        # 오래된 것부터 집는다. 최신 것만 집으면 이번에 빠진 대화가 다음
        # 폴링의 lookback 창 밖으로 밀려나 영구히 구멍이 된다.
        selected = sorted(
            markers_by_chat_id.items(),
            key=lambda item: (item[1] or _UNKNOWN_MARKER, item[0]),
        )[: max(0, limit)]

        envelopes: list[SourceChangeEnvelope] = []
        for chat_id, marker in selected:
            envelope = await self._build_envelope(
                chat_id=chat_id,
                workspace_id=workspace_id,
                ordering_marker=marker,
                observed_at=observed_at,
                max_pages=max_pages,
            )
            if envelope is not None:
                envelopes.append(envelope)
        return envelopes

    async def _list_changed_chats(
        self,
        *,
        lookback_start: datetime,
        max_pages: int,
        states: Sequence[str],
    ) -> dict[str, datetime | None]:
        """state별 목록을 훑어 바뀐 대화 id와 증분 기준 시각을 모은다.

        같은 대화가 여러 state 목록에 나오면 한 건으로 합치고, 기준 시각은
        더 최신 쪽을 남긴다.
        """
        page_limit = max(1, max_pages)
        markers_by_chat_id: dict[str, datetime | None] = {}

        for state in states:
            cursor: str | None = None
            page_count = 0
            while True:
                page = await self._client.list_user_chats(
                    self._access_key,
                    self._access_secret,
                    channel_id=self._channel_id,
                    state=state,
                    since=cursor,
                    sort_order="desc",
                )
                page_count += 1

                reached_boundary = False
                for item in page.items:
                    marker = item.ordering_marker
                    if marker is not None and marker < lookback_start:
                        # 경계에 닿아도 이 페이지는 끝까지 본다. 목록이
                        # 시각순으로 완전히 정렬되어 있다고 믿지 않는다.
                        reached_boundary = True
                        continue
                    _remember_marker(markers_by_chat_id, item.user_chat_id, marker)

                if (
                    reached_boundary
                    or page.next_cursor is None
                    or page_count >= page_limit
                ):
                    break
                cursor = page.next_cursor

        return markers_by_chat_id

    async def _build_envelope(
        self,
        *,
        chat_id: str,
        workspace_id: int,
        ordering_marker: datetime | None,
        observed_at: datetime,
        max_pages: int,
    ) -> SourceChangeEnvelope | None:
        """대화 한 건의 상세와 메시지를 envelope로 봉한다.

        조회에 실패하면 None을 낸다. 대화 한 건의 실패로 폴링 전체를 버리면
        멀쩡한 나머지까지 다음 회차로 밀리기 때문이다.
        """
        try:
            detail = await self._client.get_user_chat(
                self._access_key,
                self._access_secret,
                channel_id=self._channel_id,
                user_chat_id=chat_id,
            )
            messages = await self._fetch_messages(
                chat_id=chat_id,
                max_pages=max_pages,
            )
        except Exception as error:
            logger.warning(
                "channel_talk_poll_chat_failed",
                user_chat_id=chat_id,
                error=str(error),
            )
            return None

        updated = detail.timing.updated_at or ordering_marker or observed_at
        source_version_key = str(int(updated.timestamp() * 1000))
        idempotency_key = f"{chat_id}-{source_version_key}"

        payload = {
            "schema_version": PAYLOAD_SCHEMA_VERSION,
            "detail": detail.model_dump(mode="json", exclude_none=True),
            "messages": [
                message.model_dump(mode="json", exclude_none=True)
                for message in messages
            ],
        }

        return SourceChangeEnvelope(
            schema_version=1,
            event_id=idempotency_key,
            workspace_id=workspace_id,
            source_type=SOURCE_TYPE,
            source_identity=SourceIdentityPayload(
                entity_type=ENTITY_TYPE,
                scope_id=self._channel_id,
                target_id=self._channel_id,
                external_document_id=chat_id,
            ),
            change_kind=_resolve_change_kind(
                detail.timing.created_at,
                detail.timing.updated_at,
            ),
            source_version_key=source_version_key,
            title=detail.name,
            canonical_url=None,
            content=json.dumps(payload, ensure_ascii=False),
            content_type=CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
            source_updated_at=updated,
            observed_at=observed_at,
            idempotency_key=idempotency_key,
            metadata={},
        )

    async def _fetch_messages(
        self,
        *,
        chat_id: str,
        max_pages: int,
    ) -> list[ChannelTalkUserChatMessage]:
        """대화의 메시지를 시간순으로 끝까지 받는다.

        페이지 수 상한은 목록 순회와 같다. 커서가 끝나지 않는 응답에 갇히지
        않으려면 한 대화에도 같은 한도가 필요하다.
        """
        page_limit = max(1, max_pages)
        messages: list[ChannelTalkUserChatMessage] = []
        cursor: str | None = None
        page_count = 0
        while True:
            page = await self._client.list_user_chat_messages_page(
                self._access_key,
                self._access_secret,
                channel_id=self._channel_id,
                user_chat_id=chat_id,
                cursor=cursor,
                sort_order="asc",
            )
            page_count += 1
            messages.extend(page.messages)
            if page.next_cursor is None or page_count >= page_limit:
                break
            cursor = page.next_cursor
        return messages


def _remember_marker(
    markers_by_chat_id: dict[str, datetime | None],
    chat_id: str,
    marker: datetime | None,
) -> None:
    """대화별로 가장 최신 기준 시각만 남긴다."""
    if chat_id not in markers_by_chat_id:
        markers_by_chat_id[chat_id] = marker
        return

    previous = markers_by_chat_id[chat_id]
    if previous is None or (marker is not None and marker > previous):
        markers_by_chat_id[chat_id] = marker


def _resolve_change_kind(
    created_at: datetime | None,
    updated_at: datetime | None,
) -> ChangeKind:
    """생성 이후 손댄 적이 있는지로 변경 종류를 나눈다."""
    if created_at is not None and updated_at is not None and created_at != updated_at:
        return ChangeKind.UPDATED
    return ChangeKind.CREATED
