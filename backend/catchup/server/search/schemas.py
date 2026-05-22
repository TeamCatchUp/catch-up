from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import SourceType
from catchup.rag.schemas.sources import SourceResponse


class ManualSearchResponse(BaseModel):
    results: list[SourceResponse] = Field(..., description="검색 결과 목록")
    total: int = Field(..., description="전체 결과 수 (최대 200)")
    source_distribution: dict[str, int] = Field(
        ..., description="전체 결과의 출처별 문서 수"
    )


class ManualSearchHistoryResponse(BaseModel):
    id: int = Field(..., description="검색 기록 고유 ID")
    query: str = Field(..., description="검색어")
    created_at: datetime = Field(..., description="검색 시각")

    model_config = ConfigDict(from_attributes=True)


class OriginalContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: SourceType = Field(..., description="원문 조회 대상 connector")
    document_id: str = Field(..., min_length=1, description="검색 결과 document id")
    next_cursor: str | None = Field(
        default=None,
        description="추가 페이지 조회용 cursor",
    )


class OriginalContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: SourceType
    entity_type: str
    document_id: str
    title: str
    url: str | None = None
    items: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    next_cursor: str | None = None
    fetched_at: datetime
