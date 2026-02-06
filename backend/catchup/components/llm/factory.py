from enum import StrEnum
from functools import lru_cache


from catchup.components.llm.service import (
    AwsBedrockLlmService,
    BaseLlmService,
    OpenAiLlmService
)

class LlmProvider(StrEnum):
    OPENAI = "openai"
    AWS_BEDROCK = "aws-bedrock"
    

@lru_cache(maxsize=1)
def get_llm_service(provider: LlmProvider) -> BaseLlmService:
    if provider == LlmProvider.OPENAI:
        return OpenAiLlmService()
    
    if provider == LlmProvider.AWS_BEDROCK:
        return AwsBedrockLlmService()
