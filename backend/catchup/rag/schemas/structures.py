from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from catchup.db.models import SourceType


class BaseSearchQuery(BaseModel):
    reasoning: str = Field(default="", description="이 검색이 필요한 이유")
    start_date: datetime | None = Field(
        None,
        description="""
        Vector 검색 대상 문서의 발생(생성/수정) 기준 시작일.
        반드시 'YYYY-MM-DDTHH:MM:SS' 형식의 ISO 8601 포맷으로 작성할 것.
        (시간 특정 불가 시 null)
        """,
    )
    end_date: datetime | None = Field(
        None,
        description="""
        Vector 검색 대상 문서의 발생(생성/수정) 기준 종료일.
        반드시 'YYYY-MM-DDTHH:MM:SS' 형식의 ISO 8601 포맷으로 작성할 것.
        (시간 특정 불가 시 null)
        """,
    )


class VectorDbSearchQuery(BaseSearchQuery):
    query: str = Field(..., description="Vector 검색 엔진에 전달할 최적화된 검색어")
    keyword_tokens: list[str] = Field(
        default_factory=list,
        description="Tier 1/2 식별자 수준의 키워드만 포함 (클래스명·함수명·티켓ID·고유 명사). generic 단어(token, API, data 등)는 제외. 해당 없으면 빈 리스트.",
    )


class ManualSearchQuery(VectorDbSearchQuery):
    query: str = Field(
        default="",
        description=(
            "hybrid 모드: 벡터 검색에 전달할 English 쿼리 (번역 + 동의어 확장). "
            "keyword_only 모드: 사용되지 않으므로 빈 문자열."
        ),
    )
    search_mode: Literal["keyword_only", "hybrid"] = Field(
        default="hybrid",
        description=(
            "keyword_only: 벡터 검색 없이 pg_bigm 키워드 검색만 수행. "
            "entity lookup(브랜드명·고유명사·식별자)에 사용. "
            "hybrid: 벡터 + 키워드 병렬 검색. keyword_tokens가 비어 있으면 벡터 단독."
        ),
    )


class VectorDbSearchPlan(BaseModel):
    reasoning: str = Field(
        default="",
        description="이 검색 방향을 선택한 이유 (Korean, 1 sentence)",
    )
    queries: list[VectorDbSearchQuery] = Field(
        default_factory=list,
        min_length=0,
        max_length=3,
        description="사용자의 의도를 분석하여 생성된 독립적인 검색 쿼리 목록",
    )


class MultiSearchRequest(BaseModel):
    query: str = Field(description="벡터 DB에 전달할 시맨틱 검색어")
    keyword_tokens: list[str] | None = Field(
        default=None,
        description="Tier 1/2 식별자 수준의 키워드만 포함 (클래스명·함수명·티켓ID·고유 명사). generic 단어는 제외. 해당 없으면 null.",
    )
    start_date: str | None = Field(
        default=None,
        description="Vector 검색 대상 문서의 발생(생성/수정) 기준 시작일. 반드시 'YYYY-MM-DDTHH:MM:SS' 형식의 UTC ISO 8601 포맷으로 작성할 것.",
    )
    end_date: str | None = Field(
        default=None,
        description="Vector 검색 대상 문서의 발생(생성/수정) 기준 종료일. 반드시 'YYYY-MM-DDTHH:MM:SS' 형식의 UTC ISO 8601 포맷으로 작성할 것.",
    )


class SearchTurnMeta(BaseModel):
    """단일 검색 턴의 경량 메타데이터.

    doc_ids만 보존하고 full Document는 저장하지 않는다.
    search_turn_history 리스트 내 순서(1-based)가 supervisor에게 노출되는 ID 역할을 한다.
    turn_number는 디버깅/로깅용으로만 사용한다.
    """

    turn_number: int
    rewritten_query: str
    query_topic: str | None
    doc_ids: list[str]
    source_distribution: dict[str, int]


# Supervisor가 결정하는 파이프라인 실행 계획
class PipelinePlan(BaseModel):
    reasoning: str = Field(
        default="",
        description="이 파이프라인 타입을 선택한 이유 및 분석 결과"
    )
    pipeline_type: Literal["direct_answer", "reuse", "simple", "standard", "complex", "clarify"] = Field(
        description="실행할 파이프라인 타입"
    )
    max_iterations: int = Field(
        default=3,
        description="ReAct 루프 최대 반복 횟수. simple=0, standard=3, complex=7",
    )
    clarification_question: str | None = Field(
        default=None,
        description=(
            "clarify 타입일 때만 채운다. "
            "사용자에게 보낼 명확화 질문 (사용자 언어와 동일한 언어로 작성)."
        ),
    )
    inferred_tool_filters: list[SourceType] | None = Field(
        default=None,
        description=(
            "쿼리가 특정 협업 툴 소스를 명시적으로 지정할 때만 채운다 "
            "(예: 'Jira에서', 'Slack에서'). "
            "소스가 불명확하거나 ID·토픽 기반 쿼리처럼 cross-source 가능성이 있으면 null."
        ),
    )
    query_topic: str | None = Field(
        default=None,
        description=(
            "reuse / simple / standard / complex 파이프라인일 때만 채운다. "
            "질문의 핵심 주제를 3~5단어의 한국어 명사구로 작성. "
            "direct_answer 및 clarify일 때는 null."
        ),
    )
    reuse_history_turn_numbers: list[int] | None = Field(
        default=None,
        description=(
            "reuse 파이프라인일 때만 채운다. "
            "null이면 hot cache만 사용. "
            "값을 지정하면 해당 1-based 인덱스의 검색 턴 문서만 사용 (hot cache 자동 포함 안 됨). "
            "hot cache를 포함하려면 search_history에서 '(hot cache)' 표시된 턴의 인덱스도 포함. "
            "예: [1] → Search 1만. [1, 3] where Search 3이 hot cache → Search 1 + hot cache."
        ),
    )


# Complex 파이프라인 planner가 생성하는 검색 단계
class SearchStep(BaseModel):
    step: int = Field(description="실행 순서")
    intent: str = Field(description="이 단계에서 찾으려는 정보의 의도")
    queries: list[str] = Field(description="실행할 검색 쿼리 목록")
    keyword_tokens: list[str] = Field(
        default_factory=list,
        description="Tier 1/2 식별자 수준의 키워드만 포함 (클래스명·함수명·티켓ID·고유 명사). generic 단어(token, API, data 등)는 제외. 해당 없으면 빈 리스트.",
    )
    parallel: bool = Field(
        default=False,
        description="True면 queries를 병렬 실행 (multi_query_search 사용)",
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="이 단계를 실행하기 전에 완료되어야 하는 선행 step 번호 목록",
    )


# Complex planner LLM 응답 스키마
class SearchPlan(BaseModel):
    steps: list[SearchStep] = Field(
        default_factory=list, description="순서대로 실행할 검색 단계 목록"
    )
