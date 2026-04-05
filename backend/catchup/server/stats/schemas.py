from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class ModelTokenCostSchema(BaseModel):
    input_tokens: int
    output_tokens: int
    usd: float


class UserChatTokenUsageResponse(BaseModel):
    total_usd: float = Field(..., description="합산 비용 (USD)")
    by_model: dict[str, ModelTokenCostSchema] = Field(..., description="모델별 토큰 사용량 및 비용")
    start_date: datetime | None = Field(None, description="집계 시작일")
    end_date: datetime | None = Field(None, description="집계 종료일")