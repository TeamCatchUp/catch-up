from functools import lru_cache

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.service import AwsBedrockLlmService
from catchup.components.llm.service import BaseLlmService
from catchup.components.llm.service import ModelCapacity
from catchup.components.llm.service import OpenAiLlmService


@lru_cache(maxsize=16)
def get_llm_service(
    provider: LlmProvider,
    model_capacity: ModelCapacity,
    streaming: bool = True,
    isolated: bool = False,
    extended_thinking: bool = False,
    thinking_budget_tokens: int = 8000,
) -> BaseLlmService:
    if provider == LlmProvider.OPENAI:
        return OpenAiLlmService(
            model_capacity=model_capacity,
            streaming=streaming
        )

    if provider == LlmProvider.AWS_BEDROCK:
        return AwsBedrockLlmService(
            model_capacity=model_capacity,
            streaming=streaming,
            isolated=isolated,
            extended_thinking=extended_thinking,
            thinking_budget_tokens=thinking_budget_tokens,
        )

    raise ValueError(f"Unknown provider: {provider}")