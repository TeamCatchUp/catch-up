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
    
    usage = response.usage_metadata
    if not usage:
        return {"token_breakdown": {}}
    
    metadata = response.response_metadata
    model = (
        metadata.get("model_id")
        or metadata.get("model_name")
        or "unknown"
    )
        
    return {
        "token_breakdown": {
            model: {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
        }
    }