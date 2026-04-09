from typing import TypedDict

from langchain_core.messages import AIMessage


class _TokenUsage(TypedDict):
    token_breakdown: dict[str, dict[str, int]]


def extract_token_usages(
    response: AIMessage
) -> _TokenUsage:
    """
    AIMessage로부터 추론 모델과 토큰 사용량 (input/output)을 추출하는 유틸 함수.
    ctx.add_tokens()에 바로 넘길 수 있는 형태로 반환한다.
    """
    
    usages = response.usage_metadata
    if not usages:
        return {"token_breakdown": {}}
    
    metadata = response.response_metadata
    model = (
        metadata.get("model_id")
        or metadata.get("model_name")
        or "unknown"
    )
    
    cache_usages = usages.get("input_token_details") or {}

    return {
        "token_breakdown": {
            model: {
                "input_tokens": usages.get("input_tokens", 0),
                "output_tokens": usages.get("output_tokens", 0),
                "cache_read_tokens": cache_usages.get("cache_read", 0),
                "cache_write_tokens": cache_usages.get("cache_creation", 0),
            }
        }
    }