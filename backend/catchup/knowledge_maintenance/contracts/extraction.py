"""Extractor와 주고받는 데이터의 계약을 정의한다.

입력과 출력이 함께 있다. 둘 다 LLM이라는 바깥과 오가는 형태이므로 한쪽만
바꿀 수 없고, 도메인이 소유한 개념과도 구분된다.

Candidate끼리는 database ID가 아니라 한 번의 추출 안에서만 유효한
`local_key`로 서로를 가리킨다. 저장 시점에 repository가 실제 ID를 발급한다.

이 계약은 아직 canonical knowledge가 아니다. 여기 담긴 값은 검증되지 않은
LLM 출력이며, resolution과 승인 경계를 지나야 확정 지식이 된다.
"""

from __future__ import annotations

import re
from datetime import UTC
from datetime import datetime
from typing import Annotated
from typing import Literal
from typing import Self

from pydantic import AfterValidator
from pydantic import BaseModel
from pydantic import BeforeValidator
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.source_version import JsonValue

# 레이어 1이 이미 확정한 Entity를 가리키는 참조 키다. Extractor가 만든 것이
# 아니라 요청에 실려 들어온 것이므로 `m1`, `m2`처럼 따로 표기하고, batch의
# `entities`에는 담기지 않는다. 고객이 무엇을 물었는지 같은 관계는 이 키를
# 한쪽 끝으로 삼아야만 표현할 수 있다.
METADATA_LOCAL_KEY_PATTERN = re.compile(r"^m\d+$")


def metadata_local_key(index: int) -> str:
    """metadata Entity가 이번 추출에서 쓸 참조 키를 만든다."""
    return f"m{index}"


def is_metadata_local_key(value: str) -> bool:
    """이미 확정된 Entity를 가리키는 키인지 본다."""
    return METADATA_LOCAL_KEY_PATTERN.match(value) is not None


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


# 부분 날짜(연도만, 연-월)를 걸러내기 위한 형태다. 프롬프트는 claim의 값에는
# `YYYY`, `YYYY-MM`도 허용하지만 valid_from/valid_to는 완전한 달력 날짜만
# 받는다. 두 형식을 한 validator에서 구분하기 위해 date-only만 따로 본다.
_DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BARE_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?$")


def _normalize_validity_bound(value: object) -> object:
    """validity 경계 값을 UTC aware datetime으로만 받아들인다.

    프롬프트는 valid_from/valid_to를 완전한 달력 날짜(`YYYY-MM-DD`)나 완전한
    시각으로만 쓰라고 지시하며, 확정할 수 없으면 비우라고 한다. 이 validator는
    그 형식 계약을 계약 자체에서 한 번 더 막는다.

    숫자와 숫자로만 이루어진 문자열은 거부한다. pydantic이 `"2026"`을 Unix
    timestamp 2,026초로 읽어 1970-01-01로 조용히 바꿔놓기 때문이다. 잘못된
    시점을 지식으로 저장하는 것보다 시끄럽게 거부하는 편이 낫다.

    `YYYY-MM-DD`는 그 날 자정으로 읽는다. tz를 붙이는 일은 파싱이 끝난 뒤
    `_as_utc`가 맡는다.
    """
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, (int, float)):
        raise ValueError(
            "validity bound must be a full calendar date or datetime string, "
            "not a number"
        )
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if _BARE_NUMBER_PATTERN.match(text):
            raise ValueError(
                "validity bound must be a full calendar date "
                f"(YYYY-MM-DD), got a partial or numeric value: {text!r}"
            )
        if _DATE_ONLY_PATTERN.match(text):
            return datetime.strptime(text, "%Y-%m-%d")
        return text
    return value


def _as_utc(value: datetime | None) -> datetime | None:
    """tz 없는 경계 값을 UTC로 읽는다.

    문자열이 pydantic을 거쳐 datetime이 된 뒤에야 tzinfo를 알 수 있으므로
    aware화는 파싱 이후에 한 번 더 한다.
    """
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# 두 draft가 같은 규칙을 쓰도록 경계 타입을 한 곳에서 정의한다.
ValidityBound = Annotated[
    datetime | None,
    BeforeValidator(_normalize_validity_bound),
    AfterValidator(_as_utc),
]


class EntityCandidateDraft(BaseModel):
    """이름과 type을 가진 대상 identity 후보를 표현한다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_key: str
    proposed_type: str
    proposed_name: str
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("local_key", "proposed_type", "proposed_name")
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, info.field_name)


class ClaimCandidateDraft(BaseModel):
    """Entity가 가진 값에 대한 주장 후보를 표현한다.

    자유 텍스트 문장이 아니라 `subject + predicate + value` 구조로 받는다.
    충돌 판정이 subject와 predicate의 일치로 정의되기 때문이다.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_key: str
    subject_local_key: str
    predicate: str
    value_type: str
    value: JsonValue
    # 원문에서 이 주장을 뒷받침하는 문구다. 서버가 offset을 다시 찾는다.
    statement: str
    valid_from: ValidityBound = None
    valid_to: ValidityBound = None

    @field_validator(
        "local_key",
        "subject_local_key",
        "predicate",
        "value_type",
        "statement",
    )
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, info.field_name)


class RelationAssertionCandidateDraft(BaseModel):
    """두 Entity 사이의 관계 주장 후보를 표현한다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    local_key: str
    source_local_key: str
    target_local_key: str
    relation_type: str
    assertion_text: str
    valid_from: ValidityBound = None
    valid_to: ValidityBound = None

    @field_validator(
        "local_key",
        "source_local_key",
        "target_local_key",
        "relation_type",
        "assertion_text",
    )
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, info.field_name)


class KnowledgeCandidateBatch(BaseModel):
    """한 번의 추출이 만든 지식 후보 전체를 묶는다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entities: tuple[EntityCandidateDraft, ...] = ()
    claims: tuple[ClaimCandidateDraft, ...] = ()
    relation_assertions: tuple[RelationAssertionCandidateDraft, ...] = ()

    @model_validator(mode="after")
    def validate_local_key_graph(self) -> Self:
        """local_key가 유일하고 모든 참조가 해소되는지 검사한다.

        `m1` 같은 metadata 참조는 이 batch 안에 없어도 통과시킨다. 그 Entity는
        레이어 1이 이미 확정했고 요청에 실려 들어오므로, batch만 보고는 존재
        여부를 알 수 없다. 실제로 요청에 있었는지는
        `validate_metadata_references`가 확인한다.
        """
        keys = [
            *(entity.local_key for entity in self.entities),
            *(claim.local_key for claim in self.claims),
            *(relation.local_key for relation in self.relation_assertions),
        ]
        duplicated = {key for key in keys if keys.count(key) > 1}
        if duplicated:
            raise ValueError(f"local_key가 중복됐다: {sorted(duplicated)}")

        reserved = [
            entity.local_key
            for entity in self.entities
            if is_metadata_local_key(entity.local_key)
        ]
        if reserved:
            raise ValueError(
                f"metadata 참조로 예약된 local_key를 새 Entity에 쓸 수 없다: "
                f"{sorted(reserved)}"
            )

        entity_keys = {entity.local_key for entity in self.entities}

        for claim in self.claims:
            if not _resolves(claim.subject_local_key, entity_keys):
                raise ValueError(
                    f"claim {claim.local_key}의 subject를 찾을 수 없다: "
                    f"{claim.subject_local_key}"
                )

        for relation in self.relation_assertions:
            for endpoint in (
                relation.source_local_key,
                relation.target_local_key,
            ):
                if not _resolves(endpoint, entity_keys):
                    raise ValueError(
                        f"relation {relation.local_key}의 endpoint를 찾을 수 "
                        f"없다: {endpoint}"
                    )

        return self

    def metadata_references(self) -> frozenset[str]:
        """이 batch가 가리킨 metadata Entity의 참조 키를 모은다."""
        referenced = {
            claim.subject_local_key
            for claim in self.claims
            if is_metadata_local_key(claim.subject_local_key)
        }
        for relation in self.relation_assertions:
            for endpoint in (
                relation.source_local_key,
                relation.target_local_key,
            ):
                if is_metadata_local_key(endpoint):
                    referenced.add(endpoint)
        return frozenset(referenced)

    def validate_metadata_references(self, known_keys: frozenset[str]) -> None:
        """가리킨 metadata Entity가 실제로 요청에 있었는지 확인한다.

        모델 검증에서 분리한 이유는 요청을 알아야 판단할 수 있기 때문이다.
        Extractor가 결과를 받은 직후에 부른다.
        """
        unknown = self.metadata_references() - known_keys
        if unknown:
            raise ValueError(
                f"요청에 없는 metadata Entity를 가리켰다: {sorted(unknown)}"
            )


def _resolves(local_key: str, entity_keys: set[str]) -> bool:
    """참조가 이 batch의 Entity나 metadata Entity를 가리키는지 본다."""
    return local_key in entity_keys or is_metadata_local_key(local_key)


class EntityTypeEntry(BaseModel):
    """entity 종류 하나의 사전 항목을 정의한다.

    identity_scope가 anchored면 이 종류의 이름은 소속(조직) 없이는
    지시 대상이 정해지지 않는다. judge는 소속 근거 없이 병합을
    제안하지 않는다.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    definition: str
    identity_scope: Literal["standalone", "anchored"]
    examples: tuple[str, ...] = ()


class PredicateEntry(BaseModel):
    """claim 속성 하나의 사전 항목을 정의한다."""

    model_config = ConfigDict(frozen=True)

    name: str
    definition: str
    domain: tuple[str, ...] = ()
    value_type: Literal["number", "date", "boolean", "enum", "text"]
    enum_values: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _enum_needs_values(self) -> Self:
        if self.value_type == "enum" and not self.enum_values:
            raise ValueError("enum 치역에는 허용 값 목록이 필요하다")
        return self


class RelationTypeEntry(BaseModel):
    """관계 종류 하나의 사전 항목을 정의한다."""

    model_config = ConfigDict(frozen=True)

    name: str
    definition: str
    domain: tuple[str, ...] = ()
    range_: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


class ExtractionVocabulary(BaseModel):
    """추출이 쓸 수 있는 폐쇄 어휘를 정의한다.

    predicate와 relation type을 나눠 담는다. 한 목록으로 섞으면 값에 대한
    주장과 Entity 사이의 관계가 같은 어휘처럼 보여 오용이 생긴다.

    사전 항목(entry)이 원본이고 이름 목록은 그 파생값이다. entry가 없는
    예전 스냅샷은 이름 목록만으로도 그대로 읽힌다.

    Attributes:
        snapshot_id: 이 어휘가 어느 버전인지 식별한다.
        predicates: Claim이 쓸 수 있는 속성 이름을 나타낸다.
        relation_types: RelationAssertion이 쓸 수 있는 관계 이름을 나타낸다.
        entity_type_entries: entity 종류의 사전 항목을 담는다.
        predicate_entries: predicate의 사전 항목을 담는다.
        relation_type_entries: 관계 종류의 사전 항목을 담는다.
    """

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = ""
    predicates: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()
    entity_type_entries: tuple[EntityTypeEntry, ...] = ()
    predicate_entries: tuple[PredicateEntry, ...] = ()
    relation_type_entries: tuple[RelationTypeEntry, ...] = ()

    @model_validator(mode="after")
    def _derive_names_from_entries(self) -> Self:
        # entry가 원본이고 이름 목록은 파생값이다. v1 스냅샷은 entry가
        # 없으므로 기존 목록이 그대로 남는다.
        if self.predicate_entries and not self.predicates:
            object.__setattr__(
                self,
                "predicates",
                tuple(entry.name for entry in self.predicate_entries),
            )
        if self.relation_type_entries and not self.relation_types:
            object.__setattr__(
                self,
                "relation_types",
                tuple(entry.name for entry in self.relation_type_entries),
            )
        return self

    def predicate_entry(self, name: str) -> PredicateEntry | None:
        """이름으로 predicate 사전 항목을 찾는다."""
        for entry in self.predicate_entries:
            if entry.name == name:
                return entry
        return None

    def entity_type_entry(self, name: str) -> EntityTypeEntry | None:
        """이름으로 entity 종류 사전 항목을 찾는다."""
        for entry in self.entity_type_entries:
            if entry.name == name:
                return entry
        return None

    def is_empty(self) -> bool:
        """아직 아무 어휘도 확정되지 않았는지 나타낸다.

        entity 종류는 이름 목록으로 파생되지 않으므로 entry를 직접 본다.
        entity entry만 채운 어휘를 비었다고 보면 프롬프트의 어휘 섹션이
        통째로 빠진다.
        """
        return not (self.predicates or self.relation_types or self.entity_type_entries)


class KnowledgeExtractionRequest(BaseModel):
    """추출 한 번에 필요한 입력을 정의한다.

    저장 식별자를 담지 않는다. Extractor는 무엇이 어디에 저장되는지 모르며,
    같은 입력과 같은 계약이면 같은 결과를 내야 한다.

    Attributes:
        content: 정규화된 원문 본문을 나타낸다.
        source_type: 원문이 유입된 source 종류를 나타낸다.
        metadata_entities: 원문 밖 구조에서 이미 확정된 대상을 전달한다.
        vocabulary: 허용된 predicate와 relation type 목록을 전달한다.
        reference_time: 문서의 시간 표현을 해석할 기준 시각을 전달한다.
            원천 사건 시각이 최선이며, 없으면 절대화 지시가 내려가지 않는다.
        contract_version: 추출 계약의 버전을 나타낸다. 계약 필드가
            추가·변경되면 올린다.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    content: str
    source_type: str
    metadata_entities: tuple[MetadataEntity, ...] = ()
    # None이면 어휘 제약 없이 추출한다. 어휘를 만들기 전 관찰 단계에서 쓴다.
    vocabulary: ExtractionVocabulary | None = None
    reference_time: datetime | None = None
    contract_version: str
