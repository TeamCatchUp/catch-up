from enum import StrEnum
from functools import lru_cache

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.service import (
    AwsBedrockLlmService,
    BaseLlmService,
    ModelCapacity,
    OpenAiLlmService
)

@lru_cache(maxsize=10)
def get_llm_service(
    provider: LlmProvider,
    model_capacity: ModelCapacity
) -> BaseLlmService:
    if provider == LlmProvider.OPENAI:
        return OpenAiLlmService(model_capacity=model_capacity)
    
    if provider == LlmProvider.AWS_BEDROCK:
        return AwsBedrockLlmService(model_capacity=model_capacity)
    
    raise ValueError(f"Unknown provider: {provider}")