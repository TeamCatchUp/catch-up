from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.rag.schemas.sources import SourceResponse


class ManualSearchResponse(BaseModel):
    results: list[SourceResponse] = Field(..., description="검색 결과 목록")
    total: int = Field(..., description="전체 결과 수 (최대 200)")
    source_distribution: dict[str, int] = Field(
        ..., description="전체 결과의 출처별 문서 수"
    )
    effective_tool_filters: list[str] | None = Field(
        default=None, description="실제 적용된 협업 툴 필터"
    )
    effective_start_date: datetime | None = Field(
        default=None, description="실제 적용된 검색 시작 날짜 (UTC)"
    )
    effective_end_date: datetime | None = Field(
        default=None, description="실제 적용된 검색 종료 날짜 (UTC)"
    )
    is_tool_filter_inferred: bool = Field(
        default=False, description="협업 툴 필터가 LLM 추론으로 결정됐는지 여부"
    )
    is_date_inferred: bool = Field(
        default=False, description="날짜 필터가 LLM 추론으로 결정됐는지 여부"
    )


class ManualSearchHistoryResponse(BaseModel):
    id: int = Field(..., description="검색 기록 고유 ID")
    query: str = Field(..., description="검색어")
    created_at: datetime = Field(..., description="검색 시각")

    model_config = ConfigDict(from_attributes=True)
