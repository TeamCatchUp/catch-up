from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class DailyTokenCostSchema(BaseModel):
    from_date: datetime
    to_date: datetime
    input_tokens: int
    output_tokens: int
    usd: float



class ChatTokenUsageResponse(BaseModel):
    total_usd: float = Field(..., description="합산 비용 (USD)")
    daily_avg_usd: float = Field(..., description="일평균 비용 (USD)")
    by_date: list[DailyTokenCostSchema] = Field(..., description="일자별 토큰 사용량 및 비용")
    start_date: datetime | None = Field(None, description="집계 시작일")
    end_date: datetime | None = Field(None, description="집계 종료일")