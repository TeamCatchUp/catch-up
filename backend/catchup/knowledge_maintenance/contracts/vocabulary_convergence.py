"""어휘 자동 수렴이 주고받는 계약을 정의한다.

수렴 러너는 사전 밖(OOV) predicate·relation의 사용 현황을 모아 LLM에게
보여 주고, 동의어 병합과 사전 항목 완성을 구조화 출력으로 돌려받는다.

LLM 출력 모델은 일부러 느슨하다. `PredicateEntry`의 검증을 여기 직접
걸면 항목 하나의 결함이 전체 파싱을 무너뜨린다. 항목별 판정은 기계
가드가 맡는다.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class PredicateUsage(BaseModel):
    """predicate 하나가 pending claim 후보에서 쓰인 현황을 담는다.

    Attributes:
        name: predicate 이름을 나타낸다.
        usage_count: pending claim 후보에서 쓰인 횟수를 나타낸다.
        value_types: LLM이 신고한 값 종류의 중복 제거 목록을 나타낸다.
        observed_values: 관측된 값의 문자열 표현을 상한까지 담는다.
        example_statements: 대표 statement 예문을 상한까지 담는다.
        subject_types: subject entity 후보의 종류를 담는다.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    usage_count: int
    value_types: tuple[str, ...] = ()
    observed_values: tuple[str, ...] = ()
    example_statements: tuple[str, ...] = ()
    subject_types: tuple[str, ...] = ()


class RelationUsage(BaseModel):
    """relation type 하나가 pending 관계 후보에서 쓰인 현황을 담는다."""

    model_config = ConfigDict(frozen=True)

    name: str
    usage_count: int
    example_assertions: tuple[str, ...] = ()


class SynonymAbsorption(BaseModel):
    """OOV 이름을 기존 사전의 정본 이름으로 흡수하는 판정을 담는다.

    사전 자체는 바뀌지 않는다. 흡수는 재추출 물결에서 실체화되므로
    여기서는 판정과 이유를 감사 기록으로 남기는 것이 목적이다.
    """

    model_config = ConfigDict(frozen=True)

    candidate_name: str
    canonical_name: str
    reason: str = ""


class ProposedPredicateEntry(BaseModel):
    """LLM이 제안한 predicate 사전 항목을 담는다.

    Attributes:
        source_candidates: 이 항목이 대표하게 될 OOV 이름들을 나타낸다.
            항목 이름 자신이 관측된 경우도 근거로 친다.
        reason: 병합·정의 판단의 이유를 나타낸다. 감사 기록이 된다.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    definition: str
    value_type: str
    enum_values: tuple[str, ...] = ()
    domain: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    source_candidates: tuple[str, ...] = ()
    reason: str = ""


class ProposedRelationEntry(BaseModel):
    """LLM이 제안한 relation type 사전 항목을 담는다."""

    model_config = ConfigDict(frozen=True)

    name: str
    definition: str
    domain: tuple[str, ...] = ()
    range_: tuple[str, ...] = Field(default=())
    examples: tuple[str, ...] = ()
    source_candidates: tuple[str, ...] = ()
    reason: str = ""


class VocabularyConvergenceProposal(BaseModel):
    """수렴 한 번의 LLM 출력 전체를 담는다."""

    model_config = ConfigDict(frozen=True)

    absorptions: tuple[SynonymAbsorption, ...] = ()
    predicate_entries: tuple[ProposedPredicateEntry, ...] = ()
    relation_entries: tuple[ProposedRelationEntry, ...] = ()
