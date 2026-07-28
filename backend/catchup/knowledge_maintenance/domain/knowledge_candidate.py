from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from enum import StrEnum


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


class EntityResolutionStatus(StrEnum):
    """Entity 후보가 canonical identity로 가는 길을 나타낸다.

    Claim·RelationAssertion과 값이 다르다. Entity는 다른 Entity로 흡수되지만
    (`merged`), 주장은 같은 내용이 이미 있으면 중복이 된다(`duplicate`).
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    MERGED = "merged"
    REJECTED = "rejected"


class AssertionResolutionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ExtractionRunSpec:
    """추출을 한 번 돌릴 때 남길 실행 정보를 정의한다.

    Attributes:
        provider: 어느 LLM 제공자를 썼는지 나타낸다.
        model: 구체적인 모델 이름을 나타낸다.
        extractor_version: 추출 계약의 버전을 나타낸다.
        prompt_version: 프롬프트 템플릿의 버전을 나타낸다.
        ontology_id: 어느 어휘 체계를 따랐는지 나타낸다.
        ontology_version: 그 어휘의 스냅샷을 식별한다.
    """

    provider: str
    extractor_version: str
    ontology_id: str
    ontology_version: str
    model: str | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "provider",
            "extractor_version",
            "ontology_id",
            "ontology_version",
        ):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be blank")
            object.__setattr__(self, field_name, value)


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
    """

    run_id: uuid.UUID
    entity_ids: Mapping[str, uuid.UUID] = field(default_factory=dict)
    claim_ids: Mapping[str, uuid.UUID] = field(default_factory=dict)
    relation_ids: Mapping[str, uuid.UUID] = field(default_factory=dict)
    evidence_link_count: int = 0

    @property
    def candidate_count(self) -> int:
        """저장한 후보의 총 수를 나타낸다."""
        return len(self.entity_ids) + len(self.claim_ids) + len(self.relation_ids)
