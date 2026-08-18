"""행위자가 누구인지 판정하는 결정론 규칙을 모은다.

행위자는 source metadata에 구조로 이미 적혀 있는 확정 사실이므로 LLM 추론
대상이 아니다. 여기서 하는 일은 세 가지이고 서로 독립이다.

1. 어떤 MetadataEntity가 행위자인지 판정한다(entity_type과 external_key만 본다).
2. 같은 사람인지 묶는 동일성 키를 정한다. 이메일이 있으면 이메일, 없으면
   external_key다. 이메일이 사람 단위 식별자라 소스 세션마다 갈리는
   external_key보다 넓게 묶이기 때문이다.
3. 이름을 어느 수준까지 드러낼지(exposure) 정한다. 동일성 판정과 노출 수준은
   별개의 결정이라 같은 행위자라도 소비처에 따라 다르게 보일 수 있다.

전화번호(mobile)는 후보 attributes에 절대 싣지 않는다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.source_version import JsonValue

# seed 어휘에서 행위자를 가리키는 entity_type이다.
ACTOR_ENTITY_TYPE = "customer"

# 행위자로 볼 source metadata의 entity_type이다. 상담원(manager)은 넣지 않는다.
EXTERNAL_ACTOR_SOURCE_TYPES: Mapping[str, str] = {
    "channel_talk_user": ACTOR_ENTITY_TYPE,
}

# 후보 attributes와 노드 attributes 안에서 행위자 정보를 담는 키다.
ACTOR_ATTRIBUTE = "actor"

# 사람 이름이 아니라 역할을 가리키는 표기다. normalize_name을 거쳐 비교한다.
ROLE_LABELS: frozenset[str] = frozenset(
    {
        "고객",
        "고객사",
        "고객님",
        "사용자",
        "유저",
        "이용자",
        "customer",
        "user",
        "client",
        "lead",
    }
)

EXPOSURE_ANONYMOUS = "anonymous"
EXPOSURE_NAME = "name"
EXPOSURE_NAME_EMAIL = "name_email"
ACTOR_EXPOSURES = (EXPOSURE_ANONYMOUS, EXPOSURE_NAME, EXPOSURE_NAME_EMAIL)

# anonymous 노출에서 이름 대신 쓰는 표기다.
ANONYMOUS_LABEL = "고객"


@dataclass(frozen=True, slots=True)
class ActorIdentity:
    """source metadata에서 뽑아낸 행위자 한 명을 표현한다.

    Attributes:
        source_entity_type: 어떤 source의 어떤 대상에서 왔는지 보존한다.
        external_key: 외부 source가 부여한 식별자다.
        display_name: 사람이 알아볼 이름이다.
        email: strip·casefold로 정규화한 이메일이다.
        unified_id: 소스가 여러 세션을 한 사람으로 묶어 둔 식별자다.
        user_type: 소스가 매긴 사용자 구분이다.
    """

    source_entity_type: str
    external_key: str
    display_name: str
    email: str | None = None
    unified_id: str | None = None
    user_type: str | None = None


def _text(value: object) -> str | None:
    """문자열만 받아 공백을 걷어내고, 빈 값은 없는 것으로 본다."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalized_email(value: object) -> str | None:
    """이메일은 대소문자 표기 차이를 접어야 같은 사람으로 묶인다."""
    text = _text(value)
    return text.casefold() if text is not None else None


def actor_identity_from_metadata(entity: MetadataEntity) -> ActorIdentity | None:
    """MetadataEntity가 행위자면 identity로 옮기고, 아니면 None을 준다."""
    if entity.entity_type not in EXTERNAL_ACTOR_SOURCE_TYPES:
        return None
    external_key = _text(entity.external_key)
    if external_key is None:
        return None

    return ActorIdentity(
        source_entity_type=entity.entity_type,
        external_key=external_key,
        display_name=entity.display_name,
        email=_normalized_email(entity.attributes.get("email")),
        unified_id=_text(entity.attributes.get("unified_id")),
        user_type=_text(entity.attributes.get("user_type")),
    )


def actor_candidate_attributes(identity: ActorIdentity) -> dict[str, JsonValue]:
    """행위자 후보가 들고 다닐 attributes를 만든다.

    값이 없는 항목은 키 자체를 넣지 않는다. 전화번호는 담지 않는다.
    """
    actor: dict[str, JsonValue] = {"source_entity_type": identity.source_entity_type}
    if identity.unified_id is not None:
        actor["unified_id"] = identity.unified_id
    if identity.user_type is not None:
        actor["user_type"] = identity.user_type

    attributes: dict[str, JsonValue] = {"external_key": identity.external_key}
    if identity.email is not None:
        attributes["email"] = identity.email
    attributes[ACTOR_ATTRIBUTE] = actor
    return attributes


def actor_identity_from_candidate_attributes(
    attributes: Mapping[str, object],
    *,
    display_name: str,
) -> ActorIdentity | None:
    """후보 attributes를 identity로 되돌린다.

    ACTOR_ATTRIBUTE 키가 없으면 행위자 후보가 아니므로 None이다. display_name은
    attributes에 담기지 않으므로 호출자가 넘긴다.
    """
    actor = attributes.get(ACTOR_ATTRIBUTE)
    if not isinstance(actor, Mapping):
        return None
    source_entity_type = _text(actor.get("source_entity_type"))
    external_key = _text(attributes.get("external_key"))
    if source_entity_type is None or external_key is None:
        return None

    return ActorIdentity(
        source_entity_type=source_entity_type,
        external_key=external_key,
        display_name=display_name,
        email=_normalized_email(attributes.get("email")),
        unified_id=_text(actor.get("unified_id")),
        user_type=_text(actor.get("user_type")),
    )


def is_role_label(name: str) -> bool:
    """이름이 사람이 아니라 역할을 가리키는 표기인지 본다."""
    return normalize_name(name) in ROLE_LABELS


def actor_canonical_key(source_type: str, identity: ActorIdentity) -> str:
    """같은 행위자를 묶는 키를 만든다.

    이메일이 있으면 이메일을 쓴다. external_key는 소스 세션마다 갈릴 수 있어
    같은 사람이 여러 노드로 흩어지기 때문이다.
    """
    if identity.email is not None:
        return f"{source_type}:{ACTOR_ENTITY_TYPE}:email:{identity.email}"
    return f"{source_type}:{ACTOR_ENTITY_TYPE}:external:{identity.external_key}"


def _merged(existing: object, value: str | None) -> list[JsonValue]:
    """기존 목록에 새 값을 더해 정렬된 유니크 목록으로 만든다."""
    values = {item for item in (existing or []) if isinstance(item, str)}
    if value is not None:
        values.add(value)
    return sorted(values)


def actor_node_attributes(
    identity: ActorIdentity,
    existing: Mapping[str, object] | None,
) -> dict[str, JsonValue]:
    """행위자 노드의 attributes에 identity를 누적한다.

    한 사람이 여러 세션에 나타나므로 이메일·external_key·unified_id는 덮지 않고
    쌓는다. 기존 attributes의 다른 키는 그대로 둔다.
    """
    attributes: dict[str, JsonValue] = dict(existing or {})
    previous = attributes.get(ACTOR_ATTRIBUTE)
    previous_actor: Mapping[str, object] = (
        previous if isinstance(previous, Mapping) else {}
    )

    actor: dict[str, JsonValue] = dict(previous_actor)
    actor["source_entity_type"] = identity.source_entity_type
    actor["emails"] = _merged(previous_actor.get("emails"), identity.email)
    actor["external_keys"] = _merged(
        previous_actor.get("external_keys"), identity.external_key
    )
    actor["unified_ids"] = _merged(
        previous_actor.get("unified_ids"), identity.unified_id
    )
    if identity.user_type is not None:
        actor["user_type"] = identity.user_type

    attributes[ACTOR_ATTRIBUTE] = actor
    return attributes


def actor_display(
    display_name: str | None,
    attributes: Mapping[str, object] | None,
    exposure: str,
) -> str:
    """노출 수준에 맞춰 행위자를 부를 표기를 정한다.

    행위자가 아닌 대상은 노출 수준과 무관하게 이름을 그대로 쓴다.
    """
    actor = (attributes or {}).get(ACTOR_ATTRIBUTE)
    if not isinstance(actor, Mapping):
        return display_name or ""

    if exposure not in ACTOR_EXPOSURES:
        raise ValueError(f"unknown actor exposure: {exposure}")
    if exposure == EXPOSURE_ANONYMOUS:
        return ANONYMOUS_LABEL

    name = display_name or ""
    if exposure == EXPOSURE_NAME:
        return name

    emails = actor.get("emails") or []
    if not emails:
        return name
    return f"{name} ({emails[0]})"
