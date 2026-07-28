"""Extractor와 주고받는 데이터의 계약을 정의한다.

입력과 출력이 함께 있다. 둘 다 LLM이라는 바깥과 오가는 형태이므로 한쪽만
바꿀 수 없고, 도메인이 소유한 개념과도 구분된다.

Candidate끼리는 database ID가 아니라 한 번의 추출 안에서만 유효한
`local_key`로 서로를 가리킨다. 저장 시점에 repository가 실제 ID를 발급한다.

이 계약은 아직 canonical knowledge가 아니다. 여기 담긴 값은 검증되지 않은
LLM 출력이며, resolution과 승인 경계를 지나야 확정 지식이 된다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.source_version import JsonValue


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


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
    valid_from: datetime | None = None
    valid_to: datetime | None = None

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
    valid_from: datetime | None = None
    valid_to: datetime | None = None

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
        """local_key가 유일하고 모든 참조가 해소되는지 검사한다."""
        keys = [
            *(entity.local_key for entity in self.entities),
            *(claim.local_key for claim in self.claims),
            *(relation.local_key for relation in self.relation_assertions),
        ]
        duplicated = {key for key in keys if keys.count(key) > 1}
        if duplicated:
            raise ValueError(f"local_key가 중복됐다: {sorted(duplicated)}")

        entity_keys = {entity.local_key for entity in self.entities}

        for claim in self.claims:
            if claim.subject_local_key not in entity_keys:
                raise ValueError(
                    f"claim {claim.local_key}의 subject를 찾을 수 없다: "
                    f"{claim.subject_local_key}"
                )

        for relation in self.relation_assertions:
            for endpoint in (
                relation.source_local_key,
                relation.target_local_key,
            ):
                if endpoint not in entity_keys:
                    raise ValueError(
                        f"relation {relation.local_key}의 endpoint를 찾을 수 "
                        f"없다: {endpoint}"
                    )

        return self


class ExtractionVocabulary(BaseModel):
    """추출이 쓸 수 있는 폐쇄 어휘를 정의한다.

    predicate와 relation type을 나눠 담는다. 한 목록으로 섞으면 값에 대한
    주장과 Entity 사이의 관계가 같은 어휘처럼 보여 오용이 생긴다.

    Attributes:
        snapshot_id: 이 어휘가 어느 버전인지 식별한다.
        predicates: Claim이 쓸 수 있는 속성 이름을 나타낸다.
        relation_types: RelationAssertion이 쓸 수 있는 관계 이름을 나타낸다.
    """

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = ""
    predicates: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        """아직 아무 어휘도 확정되지 않았는지 나타낸다."""
        return not self.predicates and not self.relation_types


class KnowledgeExtractionRequest(BaseModel):
    """추출 한 번에 필요한 입력을 정의한다.

    저장 식별자를 담지 않는다. Extractor는 무엇이 어디에 저장되는지 모르며,
    같은 입력과 같은 계약이면 같은 결과를 내야 한다.

    Attributes:
        content: 정규화된 원문 본문을 나타낸다.
        source_type: 원문이 유입된 source 종류를 나타낸다.
        metadata_entities: 원문 밖 구조에서 이미 확정된 대상을 전달한다.
        vocabulary: 허용된 predicate와 relation type 목록을 전달한다.
        contract_version: 추출 계약의 버전을 나타낸다.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    content: str
    source_type: str
    metadata_entities: tuple[MetadataEntity, ...] = ()
    # None이면 어휘 제약 없이 추출한다. 어휘를 만들기 전 관찰 단계에서 쓴다.
    vocabulary: ExtractionVocabulary | None = None
    contract_version: str
