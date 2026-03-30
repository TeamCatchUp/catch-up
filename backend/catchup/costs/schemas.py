from pydantic import BaseModel, ConfigDict
from catchup.db.models import TokenPurpose

class BaseTokenUsageEvent(BaseModel):
    pass


class ChatTokenUsageEvent(BaseTokenUsageEvent):
    user_id: int
    workspace_id: int
    company_id: int
    message_id: int

    purpose: TokenPurpose = TokenPurpose.CHAT
    
    # e.g) {"claude-haiku-4-5": {"input_tokens": 1200, "output_tokens": 300}}
    token_breakdown: dict[str, dict[str, int]]
    rerank_count: int

    model_config = ConfigDict(from_attributes=True)


class EmbeddingTokenUsageResponse(BaseModel):
    total_costs_usd: float