from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from types import MappingProxyType

from catchup.knowledge_maintenance.domain.source_version import JsonValue


class ObservationKind(StrEnum):
    DOCUMENT = "document"
    TOMBSTONE = "tombstone"


# 발화 구간 지도가 담기는 `source_attributes` 키다. normalizer가 쓰고
# candidate 저장이 읽는 유일한 통로이므로 이름을 한 곳에서 정한다.
UTTERANCE_SPANS_ATTRIBUTE = "utterance_spans"


def utterance_event_at(
    source_attributes: Mapping[str, JsonValue],
    offset: int,
) -> str | None:
    """본문 offset이 속한 발화의 시각을 ISO 8601 문자열로 돌려준다.

    문서 하나에 시각을 하나만 두면 여러 날에 걸친 상담의 뒷날 발화가 상담
    시작 시각으로 앵커된다. 주장의 시간은 그 주장이 발화된 시각이어야 하므로
    claim의 근거 위치로 발화를 되짚는다.

    offset 단위는 `domain.evidence.Locator`와 같은 Unicode code point다.
    구간을 찾지 못하면 None을 돌려주고, 호출자는 문서 단위 사슬로 물러난다 —
    없는 시각을 지어내지 않는다.
    """
    spans = source_attributes.get(UTTERANCE_SPANS_ATTRIBUTE)
    if not isinstance(spans, list):
        return None
    for span in spans:
        if not isinstance(span, dict):
            continue
        start = span.get("start")
        end = span.get("end")
        at = span.get("at")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if not isinstance(at, str):
            continue
        if start <= offset < end:
            return at
    return None


@dataclass(frozen=True, slots=True)
class MetadataEntity:
    """source metadata에서 결정론적으로 뽑은 Entity 후보를 표현한다.

    Extractor LLM이 원문에서 찾는 Entity와 달리 추측이 개입하지 않는다.
    고객, 담당자, 채널처럼 원문 밖 구조에 이미 적혀 있는 대상이다.

    Attributes:
        entity_type: 대상이 어떤 종류인지 나타낸다.
        external_key: 외부 source가 부여한 식별자를 보존한다.
        display_name: 사람이 대상을 알아볼 이름을 나타낸다.
        attributes: 대상에 딸린 부가 정보를 JSON 호환 형태로 보존한다.
    """

    entity_type: str
    external_key: str | None
    display_name: str
    attributes: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("entity_type", "display_name"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be blank")
            object.__setattr__(self, field_name, value)

        object.__setattr__(
            self,
            "attributes",
            MappingProxyType(dict(self.attributes)),
        )


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    """Extractor가 읽을 수 있게 정규화한 원문을 표현한다.

    이 값은 어디에 저장되는지 모른다. `id`와 `source_version_id`는 저장
    계층이 붙인다. 같은 SourceVersion이라도 정규화 계약이 바뀌면 새
    Observation을 만들며 기존 것을 덮지 않는다.

    Attributes:
        normalizer_id: 어느 정규화 adapter가 만들었는지 나타낸다.
        normalizer_version: 정규화 계약의 버전을 나타낸다.
        observation_kind: 본문이 있는 문서인지 삭제 표식인지 나타낸다.
        content: Extractor 입력이 되는 정규화된 본문을 보존한다.
        content_hash: content의 동일 여부를 비교하는 hash를 나타낸다.
        source_attributes: 원문의 상태값을 JSON 호환 형태로 보존한다.
        metadata_entities: 결정론적으로 뽑은 Entity 후보를 보존한다.
        occurred_at: 원문에서 일이 일어난 시각을 나타낸다.
    """

    normalizer_id: str
    normalizer_version: str
    observation_kind: ObservationKind
    content: str | None
    content_hash: str | None
    source_attributes: Mapping[str, JsonValue] = field(default_factory=dict)
    metadata_entities: tuple[MetadataEntity, ...] = ()
    occurred_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in ("normalizer_id", "normalizer_version"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be blank")
            object.__setattr__(self, field_name, value)

        if self.observation_kind == ObservationKind.TOMBSTONE:
            if self.content is not None or self.content_hash is not None:
                raise ValueError(
                    "tombstone observation must not contain content"
                )
        elif not self.content:
            raise ValueError("document observation requires content")

        if self.occurred_at is not None:
            if self.occurred_at.tzinfo is None:
                raise ValueError("occurred_at must include timezone information")
            object.__setattr__(
                self,
                "occurred_at",
                self.occurred_at.astimezone(timezone.utc),
            )

        object.__setattr__(
            self,
            "source_attributes",
            MappingProxyType(dict(self.source_attributes)),
        )
        object.__setattr__(
            self,
            "metadata_entities",
            tuple(self.metadata_entities),
        )


@dataclass(frozen=True, slots=True)
class StoredObservation:
    """저장된 Observation 한 건을 표현한다.

    `NormalizedObservation`이 의도적으로 담지 않는 것을 담는다. normalizer는
    무엇이 어디에 저장되는지 몰라야 하지만, 저장된 뒤에는 그 행을 가리킬
    식별자가 필요하다. 나중에 candidate의 근거 링크가 이 `id`를 참조한다.

    Attributes:
        id: 저장된 Observation 한 건을 식별한다.
        workspace_id: Observation이 속한 CatchUp workspace를 식별한다.
        source_version_id: 정규화의 대상이 된 원문 버전을 가리킨다.
        observation: 정규화 결과 자체를 담는다.
        created_at: CatchUp이 record를 만든 시각을 나타낸다.
    """

    id: uuid.UUID
    workspace_id: int
    source_version_id: uuid.UUID
    observation: NormalizedObservation
    created_at: datetime

    def __post_init__(self) -> None:
        if self.workspace_id <= 0:
            raise ValueError("workspace_id must be greater than 0")

        if self.created_at.tzinfo is None:
            raise ValueError("created_at must include timezone information")
        object.__setattr__(
            self,
            "created_at",
            self.created_at.astimezone(timezone.utc),
        )


def content_hash(content: str) -> str:
    """정규화된 본문의 동일 여부를 비교할 hash를 만든다."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
