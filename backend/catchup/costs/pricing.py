# AWS Bedrock Model Pricing
# Pricing source: https://aws.amazon.com/bedrock/pricing/
# Last updated: 2026-03-30
# Unit: USD per token
from catchup.components.aws.utils import extract_base_model_id_from_arn

_BASE_MODEL_ID_TO_PRICING_KEY: dict[str, str] = {
    "embed-v4": "cohere.embed-v4",
    "claude-haiku-4-5": "claude-haiku-4-5",
    "claude-sonnet-4-5": "claude-sonnet-4-5",
    "rerank-v3-5": "cohere-rerank-3-5",
}

TOKEN_PRICING: dict[str, dict[str, float]] = {
    "cohere.embed-v4": {
        "input": 0.12 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input": 1.0 / 1_000_000,
        "output": 5.0 / 1_000_000,
        "input_batch": 0.5 / 1_000_000,
        "output_batch": 2.5 / 1_000_000,
    },
    "claude-sonnet-4-5": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
        "input_batch": 1.5 / 1_000_000,
        "output_batch": 7.5 / 1_000_000,
    },
}

QUERY_PRICING: dict[str, dict[str, float]] = {
    "cohere-rerank-3-5": {
        "per_query": 2.0 / 1_000,
    },
}


def resolve_pricing_key(model_id: str) -> str:
    """
    model ID (ARN 또는 raw)로부터 pricing 키를 반환한다.

    Args:
        model_id: Bedrock model ID 또는 ARN

    Raises:
        ValueError: 가격 정보가 없는 모델인 경우

    Returns:
        TOKEN_PRICING 또는 QUERY_PRICING의 키
    """
    base_model_id = extract_base_model_id_from_arn(model_id)
    pricing_key = _BASE_MODEL_ID_TO_PRICING_KEY.get(base_model_id)
    if pricing_key is None:
        raise ValueError(f"가격 정보가 없는 모델입니다: {base_model_id}")
    return pricing_key


def calc_token_cost(
    model_id: str,
    input_tokens: int, 
    output_tokens: int = 0
) -> float:
    pricing_key = resolve_pricing_key(model_id)
    pricing = TOKEN_PRICING[pricing_key]
    return (
        input_tokens * pricing.get("input", 0.0) +
        output_tokens * pricing.get("output", 0.0)
    )


def calc_query_cost(
    model_id: str,
    query_count: int
) -> float:
    pricing_key = resolve_pricing_key(model_id)
    pricing = QUERY_PRICING[pricing_key]
    return query_count * pricing["per_query"]
