from functools import lru_cache
from typing import Literal

from catchup.components.llm.service import AwsBedrockLlmService, BaseLlmService, LlmProvider, OpenAiLlmService


@lru_cache(maxsize=1)
def get_llm_service(provider: LlmProvider) -> BaseLlmService:
    if provider == LlmProvider.OPENAI:
        return OpenAiLlmService()
    
    if provider == LlmProvider.AWS_BEDROCK:
        return AwsBedrockLlmService()
