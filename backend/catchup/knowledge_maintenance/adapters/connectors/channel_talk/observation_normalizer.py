"""ChannelTalk 상담 원문을 Extractor가 읽을 형태로 정규화한다.

레이어 1이다. LLM은 개입하지 않는다. 하는 일은 하나로 요약된다.
**원문에 구조로 적혀 있는 것을 본문에서 걷어내 상태값과 Entity로 옮긴다.**

왜 필요한지는 관찰로 확인했다. 렌더링된 텍스트를 그대로 Extractor에 넣었더니
`Status: Released` 같은 소스 필드가 Claim의 87%를 차지했다. 태그나 담당자는
LLM이 추론할 대상이 아니라 이미 확정된 사실이므로, 본문에 남겨 두면 추출이
그것을 지식으로 착각한다. 프롬프트로 배제를 지시해도 걸러지지 않았다.

그래서 본문에는 사람이 실제로 한 말만 남긴다.

    고객: 오래된 매뉴얼 PDF를 올렸는데 아무 내용도 검색되지 않습니다.
    상담원: 파일 목록에는 보이는데 내용이 비어 있나요?
    [내부] 상담원: 권한 축소 후 기존 색인 제거 상태 확인 요청

화자를 이름 대신 역할로 적는 것도 같은 이유다. 이름은 `metadata_entities`에
외부 ID와 함께 실려 가므로, 본문에 다시 적으면 Extractor가 같은 사람을 또
Entity로 만든다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime

from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

# SourceVersion.content가 담고 있는 payload의 형식이다. 커넥터가 정규화한
# user chat detail과 message 목록을 JSON으로 직렬화한 것이며, ChannelTalk API
# 응답 원본이 아니다. 응답 파싱은 커넥터가 이미 끝냈다.
CHANNEL_TALK_USER_CHAT_MEDIA_TYPE = "application/vnd.channel-talk.user-chat+json"

CUSTOMER_ENTITY_TYPE = "channel_talk_user"
MANAGER_ENTITY_TYPE = "channel_talk_manager"

_CUSTOMER_ROLE = "고객"
_MANAGER_ROLE = "상담원"
_BOT_ROLE = "봇"
_PRIVATE_MARK = "[내부] "
_ATTACHMENT_PLACEHOLDER = "[파일 첨부]"

_ROLE_BY_AUTHOR_TYPE = {
    "customer": _CUSTOMER_ROLE,
    "user": _CUSTOMER_ROLE,
    "manager": _MANAGER_ROLE,
    "bot": _BOT_ROLE,
}


class ChannelTalkUserChatNormalizer:
    """ChannelTalk user chat 한 건을 NormalizedObservation으로 옮긴다."""

    normalizer_id = "channel_talk.user_chat"
    normalizer_version = "1"

    def normalize(self, source_version: SourceVersion) -> NormalizedObservation:
        if source_version.change_kind == ChangeKind.DELETED:
            return self._tombstone(source_version)

        if source_version.content_type != CHANNEL_TALK_USER_CHAT_MEDIA_TYPE:
            raise ValueError(
                "content_type must be "
                f"{CHANNEL_TALK_USER_CHAT_MEDIA_TYPE}, "
                f"got {source_version.content_type}"
            )
        if source_version.content is None:
            raise ValueError("content must not be empty")

        payload = json.loads(source_version.content)
        detail = ChannelTalkUserChatDetail.model_validate(payload["detail"])
        messages = [
            ChannelTalkUserChatMessage.model_validate(item)
            for item in payload["messages"]
        ]

        content = _render_utterances(messages)
        return NormalizedObservation(
            normalizer_id=self.normalizer_id,
            normalizer_version=self.normalizer_version,
            observation_kind=ObservationKind.DOCUMENT,
            content=content,
            content_hash=content_hash(content),
            source_attributes=_collect_attributes(detail, messages),
            metadata_entities=_collect_entities(detail),
            occurred_at=_opened_at(detail, messages),
        )

    def _tombstone(self, source_version: SourceVersion) -> NormalizedObservation:
        """삭제된 원문은 본문 없는 관찰로 남긴다.

        행을 지우지 않는다. 이 원문에서 나온 지식이 언제부터 근거를 잃었는지
        나중에 되짚을 수 있어야 하기 때문이다.
        """
        return NormalizedObservation(
            normalizer_id=self.normalizer_id,
            normalizer_version=self.normalizer_version,
            observation_kind=ObservationKind.TOMBSTONE,
            content=None,
            content_hash=None,
            source_attributes={"deleted": True},
            metadata_entities=(),
            occurred_at=source_version.source_updated_at or source_version.observed_at,
        )


def _is_lifecycle_log(message: ChannelTalkUserChatMessage) -> bool:
    """상담이 열리고 배정되고 닫힌 기록인지 본다."""
    return message.log is not None


def _submitted_form_inputs(
    message: ChannelTalkUserChatMessage,
) -> list[dict[str, JsonValue]]:
    """고객이 제출한 입력폼 항목을 읽는다.

    상담원이 입력폼을 띄우기만 한 메시지는 항목이 없고 안내 문구가 본체이므로
    일반 발화로 취급한다.
    """
    if message.form is None or not message.form.inputs:
        return []
    return [
        {"label": item.label, "value": item.value}
        for item in message.form.inputs
        if item.value is not None
    ]


def _role_of(message: ChannelTalkUserChatMessage) -> str | None:
    """발화자의 역할을 정한다."""
    if message.author is None or message.author.author_type is None:
        return None
    return _ROLE_BY_AUTHOR_TYPE.get(message.author.author_type)


def _render_utterances(messages: Iterable[ChannelTalkUserChatMessage]) -> str:
    """사람이 한 말만 골라 본문을 만든다."""
    lines: list[str] = []
    for message in messages:
        if _is_lifecycle_log(message) or _submitted_form_inputs(message):
            continue

        role = _role_of(message)
        if role is None:
            continue

        # 첨부가 있어도 사람이 함께 쓴 말은 남긴다. 파일명을 본문에서
        # 걷어내는 것과 발화를 지우는 것은 다른 일이다.
        text = (message.plain_text or "").strip()
        if message.attachments:
            text = (
                f"{text} {_ATTACHMENT_PLACEHOLDER}"
                if text
                else _ATTACHMENT_PLACEHOLDER
            )
        if not text:
            continue

        mark = _PRIVATE_MARK if message.is_private else ""
        lines.append(f"{mark}{role}: {text}")

    return "\n".join(lines)


def _collect_attributes(
    detail: ChannelTalkUserChatDetail,
    messages: list[ChannelTalkUserChatMessage],
) -> dict[str, JsonValue]:
    """본문에서 걷어낸 것과 원문 상태를 함께 보존한다."""
    lifecycle: list[JsonValue] = [
        {
            "action": message.log.action,
            "at": _moment(message.created_at),
        }
        for message in messages
        if message.log is not None
    ]
    attachments: list[JsonValue] = [
        {"name": item.name, "content_type": item.content_type}
        for message in messages
        for item in message.attachments
    ]
    buttons: list[JsonValue] = [
        button.text
        for message in messages
        for button in message.buttons
        if button.text is not None
    ]
    form_submissions: list[JsonValue] = [
        item for message in messages for item in _submitted_form_inputs(message)
    ]

    attributes: dict[str, JsonValue] = {
        "title": detail.name,
        "state": detail.state.value,
        "managed": detail.managed,
        "priority": detail.priority,
        "tags": [tag.name or tag.key for tag in detail.tags],
        "lifecycle": lifecycle,
        "attachments": attachments,
        "buttons": buttons,
        "form_submissions": form_submissions,
        "message_counts": _count_messages(messages),
        "opened_at": _moment(detail.timing.opened_at),
        "closed_at": _moment(detail.timing.closed_at),
        "first_asked_at": _moment(detail.timing.first_asked_at),
        "first_replied_at": _moment(detail.timing.first_replied_at),
        "metrics": {
            key: value
            for key, value in detail.metrics.model_dump().items()
            if value is not None
        },
    }
    return {key: value for key, value in attributes.items() if value is not None}


def _count_messages(
    messages: list[ChannelTalkUserChatMessage],
) -> dict[str, JsonValue]:
    """누가 얼마나 말했는지 센다."""
    counts = {
        "total": len(messages),
        "log": 0,
        "private": 0,
        _CUSTOMER_ROLE: 0,
        _MANAGER_ROLE: 0,
        _BOT_ROLE: 0,
    }
    for message in messages:
        if _is_lifecycle_log(message):
            counts["log"] += 1
            continue
        if message.is_private:
            counts["private"] += 1
        role = _role_of(message)
        if role is not None:
            counts[role] += 1

    return {
        "total": counts["total"],
        "log": counts["log"],
        "private": counts["private"],
        "customer": counts[_CUSTOMER_ROLE],
        "manager": counts[_MANAGER_ROLE],
        "bot": counts[_BOT_ROLE],
    }


def _collect_entities(
    detail: ChannelTalkUserChatDetail,
) -> tuple[MetadataEntity, ...]:
    """원문 밖 구조에 이미 확정된 대상을 Entity 후보로 옮긴다.

    봇은 넣지 않는다. 지식의 주체가 아니고 승인의 대상도 아니다.
    """
    entities: list[MetadataEntity] = []

    customer = detail.customer
    if customer is not None:
        entities.append(
            MetadataEntity(
                entity_type=CUSTOMER_ENTITY_TYPE,
                external_key=customer.external_user_id,
                display_name=customer.name or customer.external_user_id,
                attributes={
                    key: value
                    for key, value in (
                        ("email", customer.email),
                        ("user_type", customer.user_type),
                    )
                    if value is not None
                },
            )
        )

    assignee_id = detail.assignment.assignee_id
    for manager in detail.assignment.managers:
        if not manager.name:
            continue
        entities.append(
            MetadataEntity(
                entity_type=MANAGER_ENTITY_TYPE,
                external_key=manager.manager_id,
                display_name=manager.name,
                attributes={
                    "is_assignee": manager.manager_id == assignee_id,
                    **({"email": manager.email} if manager.email else {}),
                },
            )
        )

    return tuple(entities)


def _opened_at(
    detail: ChannelTalkUserChatDetail,
    messages: list[ChannelTalkUserChatMessage],
) -> datetime | None:
    """상담이 시작된 시각을 찾는다."""
    return (
        detail.timing.opened_at
        or detail.timing.first_opened_at
        or detail.timing.created_at
        or next(
            (
                message.created_at
                for message in messages
                if message.created_at is not None
            ),
            None,
        )
    )


def _moment(value: datetime | None) -> str | None:
    """시각을 JSON에 담을 수 있게 만든다."""
    return value.isoformat() if value is not None else None
