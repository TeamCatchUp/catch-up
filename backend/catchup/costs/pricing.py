# https://aws.amazon.com/bedrock/pricing/
# last updated at: 2026-03-30
# USD per token


ARN_TO_MODEL_KEY: dict[str, str] = {
    "global.cohere.embed-v4:0": "cohere.embed-v4",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0": "claude-haiku-4-5",
    "cohere.rerank-v3-5:0": "cohere-rerank-3-5",
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
}


QUERY_PRICING: dict[str, dict[str, float]] = {
    "cohere-rerank-3-5": {
        "per_query": 2.0 / 1_000,
    },
}


def resolve_model_key(model_part: str) -> str:
    if model_part not in ARN_TO_MODEL_KEY:
        raise ValueError(f"가격 정보가 없는 모델입니다: {model_part}")
    return ARN_TO_MODEL_KEY[model_part]


def calc_token_cost(
    model_id: str,
    input_tokens: int, 
    output_tokens: int = 0
) -> float:
    pricing = TOKEN_PRICING[model_id]
    return (
        input_tokens * pricing.get("input", 0.0) +
        output_tokens * pricing.get("output", 0.0)
    )


def calc_query_cost(
    model_id: str,
    query_count: int
) -> float:
    pricing = QUERY_PRICING[model_id]
    return query_count * pricing["per_query"]
