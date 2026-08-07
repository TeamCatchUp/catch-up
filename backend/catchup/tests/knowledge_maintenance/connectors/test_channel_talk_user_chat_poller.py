"""ChannelTalk user_chat 폴러가 수집 계약 envelope를 만드는지 검증한다.

fake client는 실제 파싱 모델을 API 원문 payload로부터 조립해 돌려준다.
파싱 계층을 우회하면 폴러가 실제 필드 이름을 잘못 읽어도 테스트가 통과하기
때문이다.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import pytest

from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessagePage,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (  # noqa: E501
    CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (  # noqa: E501
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.user_chat_poller import (  # noqa: E501
    ChannelTalkUserChatPoller,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

CHANNEL_ID = "ch-catchup-eval"
WORKSPACE_ID = 1
NOW = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)
LOOKBACK_START = NOW - timedelta(days=7)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _list_payload(
    entries: list[tuple[str, datetime | None]],
    *,
    state: str,
    next_cursor: str | None = None,
) -> dict[str, Any]:
    """user-chat 목록 API 원문을 만든다."""
    return {
        "userChats": [
            {
                "id": chat_id,
                "state": state,
                **({"updatedAt": _iso(marker)} if marker is not None else {}),
            }
            for chat_id, marker in entries
        ],
        "next": next_cursor,
    }


def _detail_payload(
    chat_id: str,
    *,
    created_at: datetime,
    updated_at: datetime | None,
    state: str = "closed",
    customer_extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """user-chat 상세 API 원문을 만든다.

    `customer_extras`로 고객 객체에 실데이터에서 관찰된 휘발 필드를 얹는다.
    """
    return {
        "userChat": {
            "id": chat_id,
            "channelId": CHANNEL_ID,
            "state": state,
            "managed": True,
            "name": f"{chat_id} 문의",
            "createdAt": _iso(created_at),
            **({"updatedAt": _iso(updated_at)} if updated_at is not None else {}),
            "openedAt": _iso(created_at),
            "assigneeId": "manager-1",
            "tags": ["요금"],
        },
        "user": {
            "id": "user-1",
            "name": "김고객",
            "type": "user",
            **(customer_extras or {}),
        },
        "managers": [
            {"id": "manager-1", "name": "박상담", "email": "pm@example.com"},
        ],
    }


def _message_payload(
    chat_id: str,
    *,
    next_cursor: str | None = None,
    with_sub_objects: bool = False,
) -> dict[str, Any]:
    """user-chat 메시지 목록 API 원문을 만든다.

    `with_sub_objects`를 켜면 blocks·log·form·webPage를 채운다. 이 중첩
    모델들은 각자 `raw_payload`를 들고 있어서 원문 유출 경로가 된다.
    """
    sub_objects: dict[str, Any] = (
        {
            "blocks": [
                {"type": "text", "value": "결제 금액이 예상과 다릅니다."},
                {"type": "text", "value": "확인 부탁드립니다."},
            ],
            "log": {
                "type": "chat.open",
                "action": "대화 시작",
                "name": "김고객",
            },
            "form": {
                "type": "profileBot",
                "submittedAt": _iso(NOW - timedelta(hours=3)),
                "inputs": [
                    {"label": "이메일", "type": "email", "value": "a@example.com"},
                ],
            },
            "webPage": {
                "url": "https://example.com/billing",
                "title": "요금 안내",
            },
        }
        if with_sub_objects
        else {}
    )
    return {
        "messages": [
            {
                "id": f"{chat_id}-m1",
                "chatId": chat_id,
                "personType": "user",
                "plainText": "결제 금액이 예상과 다릅니다.",
                "createdAt": _iso(NOW - timedelta(hours=3)),
                **sub_objects,
            },
            {
                "id": f"{chat_id}-m2",
                "chatId": chat_id,
                "personType": "manager",
                "plainText": "확인 후 답변드리겠습니다.",
                "createdAt": _iso(NOW - timedelta(hours=2)),
            },
        ],
        "next": next_cursor,
    }


class _FakeChannelTalkClient:
    """폴러가 호출하는 세 메서드만 실제 파싱 모델로 응답한다."""

    def __init__(
        self,
        *,
        list_pages: dict[str, list[dict[str, Any]]],
        details: dict[str, dict[str, Any]],
        message_pages: dict[str, list[dict[str, Any]]],
        failing_chat_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._list_pages = list_pages
        self._details = details
        self._message_pages = message_pages
        self._failing_chat_ids = failing_chat_ids
        self.list_calls: list[tuple[str, str | None]] = []
        self.detail_calls: list[str] = []

    async def list_user_chats(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        state: Any,
        since: str | None = None,
        limit: int = 500,
        sort_order: str | None = "desc",
    ) -> ChannelTalkUserChatListPage:
        resolved_state = ChannelTalkUserChatState(str(state).strip().lower())
        self.list_calls.append((resolved_state.value, since))
        pages = self._list_pages.get(resolved_state.value, [])
        index = sum(
            1 for call_state, _ in self.list_calls if call_state == resolved_state.value
        ) - 1
        if index >= len(pages):
            return ChannelTalkUserChatListPage(items=[], next_cursor=None)
        return ChannelTalkUserChatListPage.from_api_payload(
            pages[index],
            state=resolved_state,
        )

    async def get_user_chat(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        user_chat_id: str,
    ) -> ChannelTalkUserChatDetail:
        self.detail_calls.append(user_chat_id)
        if user_chat_id in self._failing_chat_ids:
            raise RuntimeError(f"detail fetch failed: {user_chat_id}")
        return ChannelTalkUserChatDetail.from_api_payload(
            self._details[user_chat_id],
            user_chat_id=user_chat_id,
        )

    async def list_user_chat_messages_page(
        self,
        access_key: str,
        access_secret: str,
        *,
        channel_id: str | None = None,
        user_chat_id: str,
        cursor: str | None = None,
        limit: int = 500,
        sort_order: str | None = "asc",
    ) -> ChannelTalkUserChatMessagePage:
        pages = self._message_pages[user_chat_id]
        index = 0 if cursor is None else int(cursor)
        return ChannelTalkUserChatMessagePage.from_api_payload(
            pages[index],
            user_chat_id=user_chat_id,
        )


def _poller(client: _FakeChannelTalkClient) -> ChannelTalkUserChatPoller:
    return ChannelTalkUserChatPoller(
        client=client,  # type: ignore[arg-type]
        access_key="key",
        access_secret="secret",
        channel_id=CHANNEL_ID,
    )


def _source_version(envelope: SourceChangeEnvelope) -> SourceVersion:
    """envelope를 그대로 SourceVersion으로 옮긴다."""
    return SourceVersion(
        id=uuid.uuid4(),
        workspace_id=envelope.workspace_id,
        source_type=envelope.source_type,
        source_identity=SourceIdentity(
            entity_type=envelope.source_identity.entity_type,
            scope_id=envelope.source_identity.scope_id,
            target_id=envelope.source_identity.target_id,
            external_document_id=envelope.source_identity.external_document_id,
        ),
        change_kind=envelope.change_kind,
        source_version_key=envelope.source_version_key,
        title=envelope.title,
        canonical_url=envelope.canonical_url,
        content=envelope.content,
        content_type=envelope.content_type,
        content_hash="a" * 64,
        source_updated_at=envelope.source_updated_at,
        observed_at=envelope.observed_at,
        idempotency_key=envelope.idempotency_key,
        payload_hash="b" * 64,
        metadata=dict(envelope.metadata),
        created_at=envelope.observed_at,
    )


@pytest.mark.asyncio
async def test_poll_builds_envelope_normalizer_can_consume() -> None:
    """폴러가 만든 envelope를 normalizer가 무수정으로 소비한다."""
    chat_id = "chat-1"
    created_at = NOW - timedelta(days=1)
    updated_at = NOW - timedelta(hours=1)
    client = _FakeChannelTalkClient(
        list_pages={
            "closed": [_list_payload([(chat_id, updated_at)], state="closed")],
        },
        details={
            chat_id: _detail_payload(
                chat_id,
                created_at=created_at,
                updated_at=updated_at,
            ),
        },
        message_pages={chat_id: [_message_payload(chat_id)]},
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=3,
        states=("closed",),
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    version_key = str(int(updated_at.timestamp() * 1000))

    assert envelope.schema_version == 1
    assert envelope.source_type == "channel_talk"
    assert envelope.content_type == CHANNEL_TALK_USER_CHAT_MEDIA_TYPE
    assert envelope.source_identity.entity_type == "user_chat"
    assert envelope.source_identity.scope_id == CHANNEL_ID
    assert envelope.source_identity.target_id == CHANNEL_ID
    assert envelope.source_identity.external_document_id == chat_id
    assert envelope.source_version_key == version_key
    assert envelope.idempotency_key == f"{chat_id}-{version_key}"
    assert envelope.event_id == envelope.idempotency_key
    assert envelope.source_updated_at == updated_at
    assert envelope.change_kind == ChangeKind.UPDATED

    payload = json.loads(envelope.content or "")
    assert payload["schema_version"] == 1
    assert payload["detail"]["user_chat_id"] == chat_id
    assert len(payload["messages"]) == 2

    observation = ChannelTalkUserChatNormalizer().normalize(
        _source_version(envelope)
    )

    assert observation.observation_kind == ObservationKind.DOCUMENT
    assert "결제 금액이 예상과 다릅니다." in observation.content
    assert "확인 후 답변드리겠습니다." in observation.content
    assert observation.source_attributes["state"] == "closed"
    assert observation.source_attributes["message_counts"]["total"] == 2


@pytest.mark.asyncio
async def test_poll_payload_carries_no_raw_api_payload() -> None:
    """payload에 API 원문 사본을 싣지 않는다.

    합성 빌더는 `raw_payload`를 채우지 않으므로, 폴러가 실으면 두 경로의
    계약이 갈린다. 게다가 payload_hash가 내용과 무관한 원문 필드까지 타서
    바뀐 것 없는 대화의 재폴링이 충돌로 터진다.
    """
    chat_id = "chat-raw"
    updated_at = NOW - timedelta(hours=1)
    client = _FakeChannelTalkClient(
        list_pages={
            "closed": [_list_payload([(chat_id, updated_at)], state="closed")],
        },
        details={
            chat_id: _detail_payload(
                chat_id,
                created_at=NOW - timedelta(days=1),
                updated_at=updated_at,
            ),
        },
        message_pages={
            chat_id: [_message_payload(chat_id, with_sub_objects=True)],
        },
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=3,
        states=("closed",),
    )

    payload = json.loads(envelopes[0].content or "")
    assert "raw_payload" not in payload["detail"]
    for message in payload["messages"]:
        assert "raw_payload" not in message

    # blocks·log·form·webPage가 실제로 채워졌는지부터 확인한다. 비어 있으면
    # 원문 유출 경로를 지나가지 않아 이 테스트가 아무것도 막지 못한다.
    first_message = payload["messages"][0]
    assert first_message["blocks"]
    assert first_message["log"]
    assert first_message["form"]["inputs"]
    assert first_message["web_page"]

    # 어느 깊이에도 남아 있지 않아야 한다.
    assert _find_keys(payload, "raw_payload") == []
    assert "raw_payload" not in (envelopes[0].content or "")


@pytest.mark.asyncio
async def test_poll_payload_drops_volatile_customer_fields() -> None:
    """고객의 휘발 필드는 payload에 싣지 않는다.

    고객 엔티티는 대화와 따로 바뀐다. 실측에서 대화의 `updatedAt`은 그대로인데
    `profile.lastReferrer`와 `updatedAt`(고객)만 달라졌다. 그 필드가 payload에
    실리면 같은 idempotency_key에 다른 payload가 붙어 재폴링이 충돌로 터진다.
    """
    chat_id = "chat-customer"
    updated_at = NOW - timedelta(hours=1)
    created_at = NOW - timedelta(days=1)

    def _client(*, referrer: str, seen_at: datetime) -> _FakeChannelTalkClient:
        return _FakeChannelTalkClient(
            list_pages={
                "closed": [_list_payload([(chat_id, updated_at)], state="closed")],
            },
            details={
                chat_id: _detail_payload(
                    chat_id,
                    created_at=created_at,
                    updated_at=updated_at,
                    customer_extras={
                        "email": "customer@example.com",
                        "profile": {"lastReferrer": referrer, "name": "김고객"},
                        "updatedAt": _iso(seen_at),
                        "lastSeenAt": _iso(seen_at),
                        "createdAt": _iso(created_at),
                        "avatarUrl": f"https://cdn.example.com/{referrer}.png",
                        "country": "kr",
                    },
                ),
            },
            message_pages={chat_id: [_message_payload(chat_id)]},
        )

    async def _poll(client: _FakeChannelTalkClient) -> SourceChangeEnvelope:
        envelopes = await _poller(client).poll(
            workspace_id=WORKSPACE_ID,
            lookback_start=LOOKBACK_START,
            limit=10,
            max_pages=3,
            states=("closed",),
        )
        assert len(envelopes) == 1
        return envelopes[0]

    first = await _poll(_client(referrer="google", seen_at=NOW - timedelta(hours=2)))
    second = await _poll(_client(referrer="naver", seen_at=NOW))

    customer = json.loads(first.content or "")["detail"]["customer"]
    assert customer == {
        "external_user_id": "user-1",
        "user_type": "user",
        "name": "김고객",
        "email": "customer@example.com",
    }
    for volatile_key in (
        "profile",
        "remote_updated_at",
        "last_seen_at",
        "remote_created_at",
        "avatar_url",
        "country",
        "channel_id",
    ):
        assert volatile_key not in customer

    # 휘발 필드만 다른 두 폴링은 같은 payload를 낸다.
    assert first.idempotency_key == second.idempotency_key
    assert first.content == second.content

    # allowlist를 통과한 뒤에도 파싱 모델로 다시 검증된다.
    ChannelTalkUserChatDetail.model_validate(
        json.loads(first.content or "")["detail"]
    )


def _find_keys(value: Any, target: str) -> list[str]:
    """중첩된 dict·list를 훑어 target 키가 나온 경로를 모은다."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == target:
                found.append(key)
            found.extend(_find_keys(item, target))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_keys(item, target))
    return found


@pytest.mark.asyncio
async def test_poll_stops_at_lookback_boundary() -> None:
    """lookback 이전 아이템을 만나면 그 페이지까지만 처리하고 멈춘다."""
    fresh = NOW - timedelta(hours=1)
    stale = LOOKBACK_START - timedelta(days=1)
    client = _FakeChannelTalkClient(
        list_pages={
            "closed": [
                _list_payload(
                    [("chat-fresh", fresh), ("chat-stale", stale)],
                    state="closed",
                    next_cursor="page-2",
                ),
                _list_payload(
                    [("chat-next-page", fresh)],
                    state="closed",
                ),
            ],
        },
        details={
            "chat-fresh": _detail_payload(
                "chat-fresh",
                created_at=fresh,
                updated_at=fresh,
            ),
        },
        message_pages={"chat-fresh": [_message_payload("chat-fresh")]},
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=5,
        states=("closed",),
    )

    # 경계 페이지는 끝까지 처리하되 다음 페이지는 요청하지 않는다.
    assert len(client.list_calls) == 1
    assert [
        envelope.source_identity.external_document_id for envelope in envelopes
    ] == ["chat-fresh"]


@pytest.mark.asyncio
async def test_poll_skips_failed_chat_and_continues() -> None:
    """대화 1건의 조회 실패는 그 대화만 빼고 폴링을 계속한다."""
    older = NOW - timedelta(hours=5)
    newer = NOW - timedelta(hours=1)
    client = _FakeChannelTalkClient(
        list_pages={
            "closed": [
                _list_payload(
                    [("chat-broken", older), ("chat-ok", newer)],
                    state="closed",
                ),
            ],
        },
        details={
            "chat-ok": _detail_payload(
                "chat-ok",
                created_at=newer,
                updated_at=newer,
            ),
        },
        message_pages={"chat-ok": [_message_payload("chat-ok")]},
        failing_chat_ids=frozenset({"chat-broken"}),
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=3,
        states=("closed",),
    )

    assert "chat-broken" in client.detail_calls
    assert [
        envelope.source_identity.external_document_id for envelope in envelopes
    ] == ["chat-ok"]


@pytest.mark.asyncio
async def test_poll_dedupes_chat_across_states() -> None:
    """같은 대화가 여러 state 목록에 나와도 envelope는 1건이다."""
    chat_id = "chat-dup"
    updated_at = NOW - timedelta(hours=2)
    client = _FakeChannelTalkClient(
        list_pages={
            "opened": [_list_payload([(chat_id, updated_at)], state="opened")],
            "closed": [_list_payload([(chat_id, updated_at)], state="closed")],
        },
        details={
            chat_id: _detail_payload(
                chat_id,
                created_at=NOW - timedelta(days=1),
                updated_at=updated_at,
            ),
        },
        message_pages={chat_id: [_message_payload(chat_id)]},
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=3,
        states=("opened", "closed"),
    )

    assert len(envelopes) == 1
    assert client.detail_calls == [chat_id]


@pytest.mark.asyncio
async def test_poll_selects_oldest_chats_when_limit_is_reached() -> None:
    """limit이 걸리면 오래된 대화부터 집어 커서 전진에 구멍을 내지 않는다."""
    oldest = NOW - timedelta(hours=6)
    middle = NOW - timedelta(hours=4)
    newest = NOW - timedelta(hours=1)
    entries = [
        ("chat-newest", newest),
        ("chat-middle", middle),
        ("chat-oldest", oldest),
    ]
    client = _FakeChannelTalkClient(
        list_pages={"closed": [_list_payload(entries, state="closed")]},
        details={
            chat_id: _detail_payload(
                chat_id,
                created_at=marker,
                updated_at=marker,
            )
            for chat_id, marker in entries
        },
        message_pages={
            chat_id: [_message_payload(chat_id)] for chat_id, _ in entries
        },
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=2,
        max_pages=3,
        states=("closed",),
    )

    assert [
        envelope.source_identity.external_document_id for envelope in envelopes
    ] == ["chat-oldest", "chat-middle"]


@pytest.mark.asyncio
async def test_poll_marks_created_when_never_updated() -> None:
    """updated_at이 created_at과 같으면 생성으로 본다."""
    chat_id = "chat-created"
    created_at = NOW - timedelta(hours=2)
    client = _FakeChannelTalkClient(
        list_pages={
            "opened": [_list_payload([(chat_id, created_at)], state="opened")],
        },
        details={
            chat_id: _detail_payload(
                chat_id,
                created_at=created_at,
                updated_at=created_at,
                state="opened",
            ),
        },
        message_pages={chat_id: [_message_payload(chat_id)]},
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=3,
        states=("opened",),
    )

    assert envelopes[0].change_kind == ChangeKind.CREATED


@pytest.mark.asyncio
async def test_poll_follows_message_cursor() -> None:
    """메시지는 next_cursor가 없어질 때까지 이어 받는다."""
    chat_id = "chat-paged"
    updated_at = NOW - timedelta(hours=1)
    client = _FakeChannelTalkClient(
        list_pages={
            "closed": [_list_payload([(chat_id, updated_at)], state="closed")],
        },
        details={
            chat_id: _detail_payload(
                chat_id,
                created_at=NOW - timedelta(days=1),
                updated_at=updated_at,
            ),
        },
        message_pages={
            chat_id: [
                _message_payload(chat_id, next_cursor="1"),
                _message_payload(chat_id),
            ],
        },
    )

    envelopes = await _poller(client).poll(
        workspace_id=WORKSPACE_ID,
        lookback_start=LOOKBACK_START,
        limit=10,
        max_pages=3,
        states=("closed",),
    )

    payload = json.loads(envelopes[0].content or "")
    assert len(payload["messages"]) == 4
