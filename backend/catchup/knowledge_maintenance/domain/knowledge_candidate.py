from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import StrEnum

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary


class ExtractionMethod(StrEnum):
    """후보가 어디서 나왔는지 나타낸다.

    결정론적 레이어가 source metadata에서 직접 뽑은 것과 Extractor LLM이
    원문에서 추론한 것은 신뢰도가 다르다. resolution이 이 둘을 같은 무게로
    다루면 안 되므로 저장 시점부터 구분한다.
    """

    DETERMINISTIC = "deterministic"
    LLM = "llm"


class ExtractionRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StoredEntityCandidate:
    """저장된 entity 후보를 resolution이 읽는 형태로 표현한다.

    Attributes:
        id: 후보 행을 식별한다.
        run_id: 후보를 만든 추출 실행을 가리킨다.
        local_key: 그 실행 안에서의 이름을 보존한다.
        proposed_type: Extractor 또는 레이어 1이 제안한 종류를 나타낸다.
        proposed_name: 제안된 표시 이름을 나타낸다.
        extraction_method: 결정론인지 LLM 추론인지 나타낸다.
        raw_payload: 저장 시점의 원본 draft를 보존한다. 결정론 후보의
            external_key가 여기 있다.
        source_type: 후보가 나온 원문의 source 종류를 나타낸다.
        created_at: 후보가 저장된 시각을 나타낸다.
        observation_excerpt: 후보가 나온 Observation 본문의 앞부분을
            담는다. identity 판정이 이름만으로 단정하지 않도록 원문
            맥락을 준다.
    """

    id: uuid.UUID
    run_id: uuid.UUID
    local_key: str
    proposed_type: str
    proposed_name: str
    extraction_method: ExtractionMethod
    raw_payload: Mapping[str, object]
    source_type: str
    created_at: datetime
    observation_excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class StoredMutationProposal:
    """저장된 mutation proposal을 resolution이 읽는 형태로 표현한다.

    Attributes:
        id: proposal 행을 식별한다.
        idempotency_key: 같은 검토 단위의 중복 생성을 막는 키를 나타낸다.
        status: proposal의 lifecycle 상태를 나타낸다.
        resolver_metadata: resolver가 남긴 판정 근거를 보존한다.
    """

    id: uuid.UUID
    idempotency_key: str
    status: str
    resolver_metadata: Mapping[str, object]


class EntityResolutionStatus(StrEnum):
    """Entity 후보가 canonical identity로 가는 길을 나타낸다.

    Claim·RelationAssertion과 값이 다르다. Entity는 다른 Entity로 흡수되지만
    (`merged`), 주장은 같은 내용이 이미 있으면 중복이 된다(`duplicate`).

    `superseded`는 사람 결정이 아니라 재추출이 구 배치를 대체할 때 붙는다.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    MERGED = "merged"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"  # 재추출이 대체한 구 배치의 후보. 사람 결정이 아니다.


class AssertionResolutionStatus(StrEnum):
    """주장 후보(Claim·RelationAssertion)의 해소 상태를 나타낸다.

    `superseded`는 사람 결정이 아니라 재추출이 구 배치를 대체할 때 붙는다.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"  # 재추출이 대체한 구 배치의 후보. 사람 결정이 아니다.


@dataclass(frozen=True, slots=True)
class ExtractionRunSpec:
    """추출을 한 번 돌릴 때 남길 실행 정보를 정의한다.

    어휘 버전을 문자열로 받지 않고 어휘 자체를 들고 있다. 실행을 기록할 때
    스냅샷도 함께 남겨야 하며, 버전만 알면 그 어휘가 무엇이었는지 되짚을 수
    없기 때문이다.

    Attributes:
        provider: 어느 LLM 제공자를 썼는지 나타낸다.
        extractor_version: 추출 계약의 버전을 나타낸다.
        ontology_id: 어느 어휘 체계를 따랐는지 나타낸다.
        vocabulary: 이 실행이 따른 어휘 스냅샷을 담는다.
        model: 구체적인 모델 이름을 나타낸다.
        prompt_version: 프롬프트 템플릿의 버전을 나타낸다.
    """

    provider: str
    extractor_version: str
    ontology_id: str
    vocabulary: ExtractionVocabulary
    model: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("provider", "extractor_version", "ontology_id"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be blank")
            object.__setattr__(self, field_name, value)

        if not self.vocabulary.snapshot_id.strip():
            raise ValueError(
                "vocabulary must carry a snapshot_id so the run can point at it"
            )

    @property
    def ontology_version(self) -> str:
        """실행이 가리킬 어휘 스냅샷의 버전을 나타낸다."""
        return self.vocabulary.snapshot_id


@dataclass(frozen=True, slots=True)
class ExtractionRun:
    """저장된 추출 실행 하나를 표현한다.

    Attributes:
        id: 실행 하나를 식별한다.
        workspace_id: 실행이 속한 CatchUp workspace를 식별한다.
        input_node_id: 입력이 된 Observation node를 가리킨다.
        status: 실행이 진행 중인지 끝났는지 나타낸다.
        started_at: 실행을 시작한 시각을 나타낸다.
        completed_at: 실행이 끝난 시각을 나타낸다.
    """

    id: uuid.UUID
    workspace_id: int
    input_node_id: uuid.UUID
    status: ExtractionRunStatus
    started_at: datetime
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.workspace_id <= 0:
            raise ValueError("workspace_id must be greater than 0")

        if self.started_at.tzinfo is None:
            raise ValueError("started_at must include timezone information")
        object.__setattr__(
            self,
            "started_at",
            self.started_at.astimezone(timezone.utc),
        )

        if self.completed_at is not None:
            if self.completed_at.tzinfo is None:
                raise ValueError("completed_at must include timezone information")
            object.__setattr__(
                self,
                "completed_at",
                self.completed_at.astimezone(timezone.utc),
            )


@dataclass(frozen=True, slots=True)
class StoredCandidateBatch:
    """한 번의 추출이 저장한 후보 전체를 표현한다.

    `local_key`에서 실제 식별자로 가는 지도가 핵심이다. Extractor는 `e1`,
    `m1`처럼 그 실행 안에서만 유효한 이름으로 서로를 가리키는데, 저장 시점에
    발급한 식별자를 이 지도가 되짚어 준다.

    Attributes:
        run_id: 이 후보들을 만든 추출 실행을 가리킨다.
        entity_ids: entity 후보의 local_key와 식별자를 잇는다.
        claim_ids: claim 후보의 local_key와 식별자를 잇는다.
        relation_ids: relation 후보의 local_key와 식별자를 잇는다.
        evidence_link_count: 남긴 근거 링크의 수를 나타낸다.
        located_claim_count: 인용을 본문에서 다시 찾은 claim의 수를 나타낸다.
        demoted_not_found_count: 인용이 본문에 없어 문서 단위 근거로 낮춘
            claim의 수를 나타낸다. 환각 의심 신호다.
        demoted_ambiguous_count: 인용이 본문에 여러 번 나와 위치를 단정하지
            못한 claim의 수를 나타낸다. 인용 자체는 진짜일 수 있다.
    """

    run_id: uuid.UUID
    entity_ids: Mapping[str, uuid.UUID] = field(default_factory=dict)
    claim_ids: Mapping[str, uuid.UUID] = field(default_factory=dict)
    relation_ids: Mapping[str, uuid.UUID] = field(default_factory=dict)
    evidence_link_count: int = 0
    located_claim_count: int = 0
    demoted_not_found_count: int = 0
    demoted_ambiguous_count: int = 0

    @property
    def candidate_count(self) -> int:
        """저장한 후보의 총 수를 나타낸다."""
        return len(self.entity_ids) + len(self.claim_ids) + len(self.relation_ids)
