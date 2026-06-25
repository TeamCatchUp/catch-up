import hashlib
import json
from datetime import datetime
from datetime import timezone
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class VerifiedConnectorWebhookEvent(BaseModel):
    """Server connector layer에서 검증한 agent-trigger용 webhook envelope."""

    source: str
    event_type: str
    payload: dict[str, Any]


class AgentWebhookEvent(BaseModel):
    """VerifiedConnectorEvent를 판정에 적합한 형태로 정규화하는 DTO."""

    event_id: str = Field(description="내부적으로 webhook event를 식별하는 고유 ID")
    external_event_id: str | None = Field(
        default=None,
        description="각 vendor가 전달한 원본 event ID",
    )
    source: str = Field(description="connector key")
    event_type: str = Field(description="내부적으로 정규화한 webhook event type")
    occurred_at: datetime | None = Field(
        default=None,
        description="Provider 기준 event 발생 시각",
    )
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="CatchUp이 event를 수신한 시각",
    )
    payload: dict[str, Any] = Field(
        description="Provider 원본 webhook payload",
    )


class AgentTriggerMatch(BaseModel):
    """AgentWebhookEvent가 등록된 trigger와 매칭된 결과."""

    trigger_id: int
    agent_spec_id: int
    event: AgentWebhookEvent
    policy_kind: str
    policy: dict[str, Any]
    entity_key: str | None = None
    reset: bool = False
    matched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentWebhookNormalizationResult(BaseModel):
    """정규화 실패도 webhook retry가 아닌 ignored 응답으로 표현하기 위한 결과."""

    event: AgentWebhookEvent | None = None
    ignored_reason: str | None = None

# TODO : Channel Talk 이외의 Webhook도 이 인터페이스를 사용하도록 점진적으로 리팩토링
def normalize_verified_connector_event(
    verified_event: VerifiedConnectorWebhookEvent,
) -> AgentWebhookNormalizationResult:
    """검증된 connector envelope을 Trigger resolver가 읽는 내부 event로 바꾼다."""
    if verified_event.source != "channel_talk":
        return AgentWebhookNormalizationResult(ignored_reason="unsupported_source")
    return _normalize_channel_talk_event(verified_event)


def _normalize_channel_talk_event(
    verified_event: VerifiedConnectorWebhookEvent,
) -> AgentWebhookNormalizationResult:
    """
    Channel Talk Payload는 event id를 제공하지 않음
    내부 idempotency는 Message/UserChat 모델의 안정 ID 조합으로 만든다.
    """
    if verified_event.payload.get("event") != "push":
        return AgentWebhookNormalizationResult(ignored_reason="unsupported_event_action")

    entity = verified_event.payload.get("entity")
    if not isinstance(entity, dict):
        return AgentWebhookNormalizationResult(ignored_reason="missing_entity")

    original_type = _text(verified_event.event_type)
    if original_type == "message":
        return _normalize_channel_talk_message_event(verified_event.payload, entity)
    if original_type == "userChat":
        return _normalize_channel_talk_user_chat_created_event(verified_event.payload, entity)
    return AgentWebhookNormalizationResult(ignored_reason="unsupported_event_type")


def _normalize_channel_talk_message_event(
    raw_payload: dict[str, Any],
    entity: dict[str, Any],
) -> AgentWebhookNormalizationResult:
    """Message webhook 중 userChat 메시지만 agent trigger 이벤트로 인정한다."""
    if entity.get("chatType") != "userChat":
        return AgentWebhookNormalizationResult(ignored_reason="unsupported_chat_type")

    channel_id = _text(entity.get("channelId"))
    if not channel_id:
        return AgentWebhookNormalizationResult(ignored_reason="missing_channel_id")

    user_chat_id = _text(entity.get("chatId"))
    if not user_chat_id:
        return AgentWebhookNormalizationResult(ignored_reason="missing_user_chat_id")

    message_id = _text(entity.get("id"))
    if not message_id:
        return AgentWebhookNormalizationResult(ignored_reason="missing_message_id")

    occurred_at = _read_channel_talk_timestamp(
        entity,
        ("createdAt", "updatedAt"),
    )
    event_type = "user_chat.new_message"

    event_id = _build_event_id(
        source="channel_talk",
        event_type=event_type,
        stable_parts=[
            channel_id,
            event_type,
            user_chat_id,
            message_id,
            occurred_at.isoformat() if occurred_at else "",
        ],
    )
    return AgentWebhookNormalizationResult(
        event=AgentWebhookEvent(
            event_id=event_id,
            source="channel_talk",
            event_type=event_type,
            occurred_at=occurred_at,
            payload=raw_payload,
        )
    )


def _normalize_channel_talk_user_chat_created_event(
    raw_payload: dict[str, Any],
    entity: dict[str, Any],
) -> AgentWebhookNormalizationResult:
    """UserChat push webhook은 새 user chat 생성 이벤트로 정규화한다."""
    channel_id = _text(entity.get("channelId"))
    if not channel_id:
        return AgentWebhookNormalizationResult(ignored_reason="missing_channel_id")

    user_chat_id = _text(entity.get("id"))
    if not user_chat_id:
        return AgentWebhookNormalizationResult(ignored_reason="missing_user_chat_id")

    refers = raw_payload.get("refers")
    if not isinstance(refers, dict):
        refers = {}
    message = refers.get("message")
    if not isinstance(message, dict):
        message = {}
    message_id = _text(message.get("id")) or None
    occurred_at = (
        _read_channel_talk_timestamp(message, ("createdAt", "updatedAt"))
        or _read_channel_talk_timestamp(
            entity,
            ("createdAt", "openedAt", "firstOpenedAt", "frontUpdatedAt"),
        )
    )
    event_type = "user_chat.created"

    event_id = _build_event_id(
        source="channel_talk",
        event_type=event_type,
        stable_parts=[
            channel_id,
            event_type,
            user_chat_id,
            message_id,
            occurred_at.isoformat() if occurred_at else "",
        ],
    )
    return AgentWebhookNormalizationResult(
        event=AgentWebhookEvent(
            event_id=event_id,
            source="channel_talk",
            event_type=event_type,
            occurred_at=occurred_at,
            payload=raw_payload,
        )
    )


def _build_event_id(
    *,
    source: str,
    event_type: str,
    stable_parts: list[str | None],
) -> str:
    """Channel Talk 모델 ID 조합으로 재처리 idempotency에 쓸 event_id 생성"""
    digest = hashlib.sha256(
        json.dumps(stable_parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:32]
    return f"{source}:{event_type}:{digest}"


def _read_channel_talk_timestamp(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> datetime | None:
    for key in keys:
        if (value := _parse_channel_talk_timestamp(payload.get(key))) is not None:
            return value
    return None


def _parse_channel_talk_timestamp(value: Any) -> datetime | None:
    """Channel Talk가 보낼 수 있는 초/밀리초/ISO 시각을 UTC datetime으로 통일"""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    text = _text(value)
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except ValueError:
            return None
    if numeric > 10_000_000_000:
        numeric = numeric / 1000
    return datetime.fromtimestamp(numeric, tz=timezone.utc)


def _text(value: Any) -> str:
    return str(value or "").strip()
