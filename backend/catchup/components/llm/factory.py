import threading

from cachetools import TTLCache
from cachetools import cached
from cachetools.keys import hashkey

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.service import AwsBedrockLlmService
from catchup.components.llm.service import BaseLlmService
from catchup.components.llm.service import ModelCapacity
from catchup.components.llm.service import OpenAiLlmService

# AWS NAT GW idle timeout(350s)보다 짧게 설정해 만료 전에 커넥션 풀 교체
_cache = TTLCache(maxsize=16, ttl=240)
# TTL 만료 시 여러 스레드가 동시에 인스턴스를 생성하는 thundering herd 방지 목적
_lock = threading.Lock()


@cached(cache=_cache, key=hashkey, lock=_lock)
def get_llm_service(
    provider: LlmProvider,
    model_capacity: ModelCapacity,
    streaming: bool = True,
    isolated: bool = False,
    extended_thinking: bool = False,
    thinking_budget_tokens: int = 8000,
    max_response_tokens: int | None = None,
    max_attempts: int = AwsBedrockLlmService.DEFAULT_MAX_ATTEMPTS,
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
            max_response_tokens=max_response_tokens,
            max_attempts=max_attempts,
        )

    raise ValueError(f"Unknown provider: {provider}")