from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.rag.schemas.sources import SourceResponse


class ManualSearchResponse(BaseModel):
    results: list[SourceResponse] = Field(..., description="검색 결과 목록")
    total: int = Field(
        ..., description="전체 결과 수 (현재는 limit에 의해 제한될 수 있음)"
    )


class ManualSearchHistoryResponse(BaseModel):
    id: int = Field(..., description="검색 기록 고유 ID")
    query: str = Field(..., description="검색어")
    created_at: datetime = Field(..., description="검색 시각")

    model_config = ConfigDict(from_attributes=True)
