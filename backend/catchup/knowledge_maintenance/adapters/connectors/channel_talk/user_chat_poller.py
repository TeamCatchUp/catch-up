"""ChannelTalk user chat을 수집 계약 envelope로 옮긴다.

폴러가 하는 일은 두 가지다. 어떤 대화가 바뀌었는지 목록으로 좁히고, 바뀐
대화의 상세와 메시지를 모아 하나의 payload로 봉한다. payload 형식은 합성
데이터 빌더(`catchup/evaluation/build_channel_talk_payloads.py`)와 같다.
normalizer가 두 경로를 구분하지 못해야 실데이터와 합성 데이터의 파이프라인
결과를 서로 대조할 수 있기 때문이다.

만든 envelope만 내지 않고 부분 수집 신호까지 함께 낸다. 러너의 증분 커서는
저장된 원문의 최신 시각에서 도출되므로, 못 집은 대화를 조용히 삼키면 그보다
최신인 대화를 저장하는 순간 커서가 빠진 대화를 지나쳐 영구 누락이 된다.

여기서는 저장도 정규화도 하지 않는다. 원문을 읽어 계약 형태로 바꾸는 것까지가
이 어댑터의 책임이고, 그 다음은 러너가 이어받는다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone

import structlog
from pydantic import BaseModel

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
from catchup.knowledge_maintenance.ports.source_poller import SkippedItem
from catchup.knowledge_maintenance.ports.source_poller import SourcePollResult

logger = structlog.get_logger(__name__)

# 부분 수집의 사유다. 러너가 문자열을 그대로 사람에게 찍는다.
SKIP_REASON_FETCH_FAILED = "fetch_failed"
SKIP_REASON_MESSAGES_TRUNCATED = "messages_truncated"

__all__ = [
    "SKIP_REASON_FETCH_FAILED",
    "SKIP_REASON_MESSAGES_TRUNCATED",
    "ChannelTalkUserChatPoller",
    "DEFAULT_STATES",
    "SkippedItem",
    "SourcePollResult",
]

SOURCE_TYPE = "channel_talk"
ENTITY_TYPE = "user_chat"
PAYLOAD_SCHEMA_VERSION = 1

DEFAULT_STATES: tuple[str, ...] = ("opened", "closed", "snoozed")

# ordering_marker를 모르는 대화의 정렬 기준이다. 가장 오래된 것으로 두어
# limit이 걸려도 먼저 집히게 한다. 판단할 근거가 없는 대화를 뒤로 미루면
# 다음 폴링에서도 계속 밀려 영영 수집되지 않는다.
_UNKNOWN_MARKER = datetime.min.replace(tzinfo=timezone.utc)

# 계약에 실리지 않는 필드다. 합성 빌더는 이 값을 채우지 않으므로 폴러도
# 빼야 두 경로의 payload가 같아진다.
_RAW_PAYLOAD_KEY = "raw_payload"

# 대화 payload에 실을 고객 필드다. normalizer가 Entity 후보를 만들 때
# 읽는 네 개가 전부다.
_CUSTOMER_KEY = "customer"
_CUSTOMER_ALLOWED_KEYS: tuple[str, ...] = (
    "external_user_id",
    "user_type",
    "name",
    "email",
)


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
    ) -> SourcePollResult:
        """lookback_start 이후 바뀐 대화를 수집 계약 envelope로 변환한다.

        만든 envelope만 내지 않고, 수집하지 못한 대화와 목록 잘림 여부를
        함께 낸다. 부분 수집 신호를 버리면 러너의 DB 파생 커서가 미수집
        대화를 지나쳐 영구 누락이 된다.
        """
        observed_at = datetime.now(timezone.utc)
        markers_by_chat_id, list_truncated = await self._list_changed_chats(
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
        skipped: list[SkippedItem] = []
        for chat_id, marker in selected:
            envelope, skip = await self._build_envelope(
                chat_id=chat_id,
                workspace_id=workspace_id,
                ordering_marker=marker,
                observed_at=observed_at,
                max_pages=max_pages,
            )
            if envelope is not None:
                envelopes.append(envelope)
            if skip is not None:
                skipped.append(skip)
        return SourcePollResult(
            envelopes=envelopes,
            skipped=skipped,
            list_truncated=list_truncated,
        )

    async def _list_changed_chats(
        self,
        *,
        lookback_start: datetime,
        max_pages: int,
        states: Sequence[str],
    ) -> tuple[dict[str, datetime | None], bool]:
        """state별 목록을 훑어 바뀐 대화 id와 증분 기준 시각을 모은다.

        같은 대화가 여러 state 목록에 나오면 한 건으로 합치고, 기준 시각은
        더 최신 쪽을 남긴다.

        두 번째 값은 목록이 잘렸는지다. 페이지 상한에 걸렸는데 다음 커서가
        아직 남아 있으면 창 하단을 못 본 것이다. 이 신호를 버리면 러너의 DB
        파생 커서가 못 본 대화를 지나쳐 영구 누락이 된다. 경계에 닿아 멈춘
        것과 커서가 끝나 멈춘 것은 창을 다 본 것이므로 잘림이 아니다.
        """
        page_limit = max(1, max_pages)
        markers_by_chat_id: dict[str, datetime | None] = {}
        truncated = False

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

                if reached_boundary or page.next_cursor is None:
                    break
                if page_count >= page_limit:
                    truncated = True
                    logger.warning(
                        "channel_talk_poll_list_truncated",
                        state=state,
                        page_limit=page_limit,
                    )
                    break
                cursor = page.next_cursor

        return markers_by_chat_id, truncated

    async def _build_envelope(
        self,
        *,
        chat_id: str,
        workspace_id: int,
        ordering_marker: datetime | None,
        observed_at: datetime,
        max_pages: int,
    ) -> tuple[SourceChangeEnvelope | None, SkippedItem | None]:
        """대화 한 건의 상세와 메시지를 envelope로 봉한다.

        envelope 대신 SkippedItem을 내는 경우가 둘이다. 조회가 실패했을
        때와, 메시지를 끝까지 못 받았을 때다. 어느 쪽이든 대화 한 건의
        문제로 폴링 전체를 버리지는 않되, 빠진 사실은 러너까지 올린다.
        부분 수집 신호를 버리면 러너의 DB 파생 커서가 이 대화를 지나쳐
        영구 누락이 된다.

        메시지가 잘렸을 때 envelope를 만들지 않는 이유가 하나 더 있다.
        버전 키는 대화의 `updatedAt`이라 완전 수집과 값이 같다. 잘린
        payload를 그 키로 봉하면, 나중에 온전히 받아 다시 넣을 때
        SourceVersionPayloadConflict로 터져 메시지를 영영 못 채운다.
        """
        try:
            detail = await self._client.get_user_chat(
                self._access_key,
                self._access_secret,
                channel_id=self._channel_id,
                user_chat_id=chat_id,
            )
            messages, messages_complete = await self._fetch_messages(
                chat_id=chat_id,
                max_pages=max_pages,
            )
        except Exception as error:
            logger.warning(
                "channel_talk_poll_chat_failed",
                user_chat_id=chat_id,
                error=str(error),
            )
            return None, SkippedItem(
                item_id=chat_id,
                ordering_marker=ordering_marker,
                reason=SKIP_REASON_FETCH_FAILED,
            )

        if not messages_complete:
            logger.warning(
                "channel_talk_poll_messages_truncated",
                user_chat_id=chat_id,
                page_limit=max(1, max_pages),
                fetched_messages=len(messages),
            )
            return None, SkippedItem(
                item_id=chat_id,
                ordering_marker=ordering_marker,
                reason=SKIP_REASON_MESSAGES_TRUNCATED,
            )

        updated = detail.timing.updated_at or ordering_marker or observed_at
        source_version_key = str(int(updated.timestamp() * 1000))
        idempotency_key = f"{chat_id}-{source_version_key}"

        # raw_payload는 봉하지 않는다. 파싱 모델이 들고 있는 API 원문을 그대로
        # 실으면 합성 빌더가 내는 payload와 형태가 갈리고, payload_hash가
        # 내용과 무관한 원문 필드까지 타게 된다. 그러면 바뀐 것이 없는 대화를
        # 다시 폴링해도 DUPLICATE로 흡수되지 않고 충돌로 터진다.
        payload = {
            "schema_version": PAYLOAD_SCHEMA_VERSION,
            "detail": _project_detail_customer(_dump_without_raw_payload(detail)),
            "messages": [
                _dump_without_raw_payload(message) for message in messages
            ],
        }

        envelope = SourceChangeEnvelope(
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
        return envelope, None

    async def _fetch_messages(
        self,
        *,
        chat_id: str,
        max_pages: int,
    ) -> tuple[list[ChannelTalkUserChatMessage], bool]:
        """대화의 메시지를 시간순으로 끝까지 받는다.

        페이지 수 상한은 목록 순회와 같다. 커서가 끝나지 않는 응답에 갇히지
        않으려면 한 대화에도 같은 한도가 필요하다.

        두 번째 값은 끝까지 받았는지다. 상한에 걸렸는데 다음 커서가 남아
        있으면 False다. 이 신호를 버리고 잘린 메시지로 envelope를 봉하면
        완전 수집과 같은 버전 키에 다른 payload가 붙어, 나중에 온전히 받아도
        충돌로 막혀 메시지를 채울 수 없다.
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
            if page.next_cursor is None:
                return messages, True
            if page_count >= page_limit:
                return messages, False
            cursor = page.next_cursor


def _dump_without_raw_payload(model: BaseModel) -> dict[str, object]:
    """파싱 모델을 계약 payload로 덮으면서 API 원문 사본을 걷어낸다.

    중첩 모델(blocks·log·form·web_page)도 각자 `raw_payload`를 들고 있어
    위 한 겹만 빼면 원문이 남는다. 그래서 덮어낸 결과를 재귀로 훑는다.
    """
    return _strip_mapping(model.model_dump(mode="json", exclude_none=True))


def _project_detail_customer(detail: dict[str, object]) -> dict[str, object]:
    """고객 객체를 normalizer가 읽는 네 필드로만 좁힌다.

    고객은 대화와 따로 사는 엔티티라서 `profile.lastReferrer`·
    `remote_updated_at`·`last_seen_at` 같은 필드가 대화와 무관하게 계속
    바뀐다. 그런데 우리 버전 키는 대화의 `updatedAt`이다. 그대로 실으면
    같은 idempotency_key에 다른 payload가 붙어, 폴링 창이 겹칠 때마다
    SourceVersionPayloadConflict로 터진다. 그래서 휘발 필드를 아예 payload
    밖에 둔다.
    """
    customer = detail.get(_CUSTOMER_KEY)
    if not isinstance(customer, dict):
        return detail

    return {
        **detail,
        _CUSTOMER_KEY: {
            key: customer[key]
            for key in _CUSTOMER_ALLOWED_KEYS
            if key in customer
        },
    }


def _strip_mapping(value: dict[str, object]) -> dict[str, object]:
    """dict에서 `raw_payload` 키를 지우고 나머지 값을 훑는다."""
    return {
        key: _strip_value(item)
        for key, item in value.items()
        if key != _RAW_PAYLOAD_KEY
    }


def _strip_value(value: object) -> object:
    """중첩된 dict·list를 따라 내려가며 원문 사본을 걷어낸다."""
    if isinstance(value, dict):
        return _strip_mapping(value)
    if isinstance(value, list):
        return [_strip_value(item) for item in value]
    return value


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
